"""
reorg_contract_column.py — move contracts into a new "Contract" column
=======================================================================
For every Monday item on the board:
  1. BACKUP: download EVERY file in its "Files" column to a local folder
             named after the project.
  2. Upload the contract file(s) -> new "Contract" column.
  3. Clear the "Files" column (Monday can only clear the whole column).
  4. Re-upload the NON-contract files back into "Files".

The "contract" is any file whose name contains: proposal / contract /
engineering services (same rule as your other scripts). Everything else
goes back into Files.

SAFETY:
  - A project's Files column is NEVER cleared unless (a) all its files
    downloaded to backup AND (b) the contract uploaded to "Contract"
    successfully. If anything fails, that project is left untouched.
  - Run --backup-only first if you want the downloads before any changes.

USAGE (from the CALCS folder):
    python reorg_contract_column.py --dry-run      # report only, no downloads, no changes
    python reorg_contract_column.py --backup-only  # download all files, NO Monday changes
    python reorg_contract_column.py                # full reorg (downloads + moves + clears)

Backup location (edit BACKUP_DIR below if you want it elsewhere):
    C:\\Users\\saxon\\OneDrive\\Documents\\PDF_AUTOMATION\\MONDAY_FILE_BACKUP

Throwaway utility — delete it when you're done.
"""

import os
import re
import sys
import json
import time
import mimetypes
import requests

from monday_config import MONDAY_API_KEY, BOARD_NAME, FILES_COLUMN

DRY_RUN     = "--dry-run" in sys.argv
BACKUP_ONLY = "--backup-only" in sys.argv

FILES_COLUMN_TITLE    = FILES_COLUMN          # "Files"
CONTRACT_COLUMN_TITLE = "Contract"            # the NEW column you made
CONTRACT_KEYWORDS     = ["proposal", "contract", "engineering services"]
BACKUP_DIR = r"C:\Users\saxon\OneDrive\Documents\PDF_AUTOMATION\MONDAY_FILE_BACKUP"

MONDAY_API_URL  = "https://api.monday.com/v2"
MONDAY_FILE_URL = "https://api.monday.com/v2/file"
HEADERS = {"Authorization": MONDAY_API_KEY, "API-Version": "2023-10"}


# =========================
# MONDAY HELPERS
# =========================

def monday_query(query, variables=None):
    resp = requests.post(
        MONDAY_API_URL, headers=HEADERS,
        json={"query": query, "variables": variables or {}},
    )
    if resp.status_code != 200:
        raise Exception(f"MONDAY API FAILED: {resp.status_code} {resp.text[:200]}")
    data = resp.json()
    if "errors" in data:
        raise Exception(f"MONDAY GRAPHQL ERROR: {data['errors']}")
    return data["data"]


def find_board_and_columns():
    data = monday_query("""
    query { boards(limit: 100) { id name columns { id title type } } }
    """)
    for board in data["boards"]:
        if board["name"].strip().lower() == BOARD_NAME.strip().lower():
            files_id = contract_id = ""
            for col in board["columns"]:
                t = col["title"].strip().lower()
                if t == FILES_COLUMN_TITLE.strip().lower():
                    files_id = col["id"]
                if t == CONTRACT_COLUMN_TITLE.strip().lower():
                    contract_id = col["id"]
            if not files_id:
                raise Exception(f"'{FILES_COLUMN_TITLE}' COLUMN NOT FOUND")
            if not contract_id:
                titles = ", ".join(c["title"] for c in board["columns"])
                raise Exception(
                    f"'{CONTRACT_COLUMN_TITLE}' COLUMN NOT FOUND. "
                    f"Make it first. Columns: {titles}"
                )
            return board["id"], files_id, contract_id
    raise Exception(f"MONDAY BOARD NOT FOUND: {BOARD_NAME}")


def fetch_all_items(board_id, files_col_id):
    """id, name, and the Files-column assets (id, name, public_url)."""
    items = []

    def collect(page):
        for it in page["items"]:
            # asset ids that belong to the Files column (from the column value JSON)
            allowed = set()
            for cv in (it.get("column_values") or []):
                if cv["id"] == files_col_id and cv.get("value"):
                    try:
                        parsed = json.loads(cv["value"])
                        for f in parsed.get("files", []):
                            aid = f.get("assetId")
                            if aid is not None:
                                allowed.add(str(aid))
                    except Exception:
                        pass
            # item-level assets carry name + download url
            assets = []
            for a in (it.get("assets") or []):
                if not allowed or str(a["id"]) in allowed:
                    assets.append({
                        "id":   a["id"],
                        "name": a["name"],
                        "url":  a.get("public_url") or a.get("url"),
                    })
            items.append({"id": it["id"], "name": it["name"], "assets": assets})

    q_first = """
    query ($board_id: [ID!], $cols: [String!]) {
      boards(ids: $board_id) {
        items_page(limit: 50) {
          cursor
          items {
            id name
            assets { id name public_url url }
            column_values(ids: $cols) { id value }
          }
        }
      }
    }
    """
    data = monday_query(q_first, {"board_id": [board_id], "cols": [files_col_id]})
    page = data["boards"][0]["items_page"]
    collect(page)
    cursor = page["cursor"]
    while cursor:
        q_next = """
        query ($cursor: String!, $cols: [String!]) {
          next_items_page(cursor: $cursor, limit: 50) {
            cursor
            items {
              id name
              assets { id name public_url url }
              column_values(ids: $cols) { id value }
            }
          }
        }
        """
        nxt = monday_query(q_next, {"cursor": cursor, "cols": [files_col_id]})
        page = nxt["next_items_page"]
        collect(page)
        cursor = page["cursor"]
    return items


def upload_to_column(item_id, column_id, file_path, file_name):
    mime = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    q = (
        f'mutation ($file: File!) {{'
        f'  add_file_to_column(item_id: {item_id}, column_id: "{column_id}", file: $file) {{ id }}'
        f'}}'
    )
    with open(file_path, "rb") as fh:
        resp = requests.post(
            MONDAY_FILE_URL,
            headers={"Authorization": MONDAY_API_KEY},
            data={"query": q},
            files={"variables[file]": (file_name, fh, mime)},
        )
    if resp.status_code != 200:
        raise Exception(f"UPLOAD FAILED: {resp.status_code} {resp.text[:200]}")
    data = resp.json()
    if "errors" in data:
        raise Exception(f"UPLOAD ERROR: {data['errors']}")


def clear_files_column(board_id, item_id, column_id):
    val = json.dumps({"clear_all": True})
    monday_query("""
    mutation ($board_id: ID!, $item_id: ID!, $col_id: String!, $val: JSON!) {
      change_column_value(board_id: $board_id, item_id: $item_id,
                          column_id: $col_id, value: $val) { id }
    }
    """, {"board_id": board_id, "item_id": item_id, "col_id": column_id, "val": val})


# =========================
# LOCAL HELPERS
# =========================

def safe_name(name):
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip() or "UNNAMED"


def is_contract(file_name):
    fn = file_name.lower()
    return any(kw in fn for kw in CONTRACT_KEYWORDS)


def download_asset(url, dest_path):
    if not url:
        raise Exception("no download URL")
    resp = requests.get(url, stream=True, timeout=60)
    if resp.status_code != 200:
        raise Exception(f"download HTTP {resp.status_code}")
    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 256):
            if chunk:
                f.write(chunk)
    if os.path.getsize(dest_path) == 0:
        raise Exception("downloaded 0 bytes")


# =========================
# MAIN
# =========================

def main():
    if DRY_RUN:
        mode = "DRY RUN (report only)"
    elif BACKUP_ONLY:
        mode = "BACKUP ONLY (download, no Monday changes)"
    else:
        mode = "FULL REORG (download + move + clear Files)"
    print(f"=== CONTRACT COLUMN REORG — {mode} ===\n")

    board_id, files_col_id, contract_col_id = find_board_and_columns()
    print("Fetching all items + files...")
    items = fetch_all_items(board_id, files_col_id)
    print(f"  {len(items)} items on board '{BOARD_NAME}'")
    if not DRY_RUN:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        print(f"  Backup folder: {BACKUP_DIR}")
    print()

    reorged      = []
    backed_up    = []
    no_files     = 0
    no_contract  = []
    errors       = []

    for it in items:
        assets = it["assets"]
        if not assets:
            no_files += 1
            continue

        contract_assets = [a for a in assets if is_contract(a["name"])]
        other_assets    = [a for a in assets if not is_contract(a["name"])]

        # ---- DRY RUN: just report ----
        if DRY_RUN:
            c = ", ".join(a["name"] for a in contract_assets) or "(none found)"
            print(f"[{it['name']}]  files={len(assets)}  contract-> {c}")
            if not contract_assets:
                no_contract.append(it["name"])
            continue

        item_dir = os.path.join(BACKUP_DIR, safe_name(it["name"]))
        os.makedirs(item_dir, exist_ok=True)

        # ---- 1. download EVERYTHING (backup) ----
        local_paths = {}
        dl_failed = False
        for a in assets:
            dest = os.path.join(item_dir, safe_name(a["name"]))
            base, ext = os.path.splitext(dest)
            n = 2
            while dest in local_paths.values():
                dest = f"{base} ({n}){ext}"
                n += 1
            try:
                download_asset(a["url"], dest)
                local_paths[a["id"]] = dest
            except Exception as e:
                dl_failed = True
                errors.append((it["name"], f"download '{a['name']}': {e}"))
                print(f"[DL ERROR]   {it['name']} / {a['name']}: {e}")
        if not dl_failed:
            backed_up.append(it["name"])

        if BACKUP_ONLY:
            if not dl_failed:
                print(f"[BACKED UP]  {it['name']}  ({len(assets)} files)")
            continue

        # ---- guard: don't touch Files unless backup is complete + a contract exists ----
        if dl_failed:
            print(f"[SKIP REORG] {it['name']}  (a download failed — Files left as-is)")
            continue
        if not contract_assets:
            no_contract.append(it["name"])
            print(f"[NO CONTRACT] {it['name']}  (Files left as-is)")
            continue

        try:
            # ---- 2. upload contract(s) to Contract column ----
            for a in contract_assets:
                upload_to_column(it["id"], contract_col_id,
                                  local_paths[a["id"]], a["name"])

            # ---- 3. clear Files column ----
            clear_files_column(board_id, it["id"], files_col_id)
            time.sleep(0.5)

            # ---- 4. re-upload non-contract files to Files ----
            for a in other_assets:
                upload_to_column(it["id"], files_col_id,
                                 local_paths[a["id"]], a["name"])

            reorged.append(it["name"])
            print(f"[REORGED]    {it['name']}  "
                  f"(contract x{len(contract_assets)} -> Contract, "
                  f"{len(other_assets)} back to Files)")
        except Exception as e:
            errors.append((it["name"], f"reorg: {e}"))
            print(f"[ERROR]      {it['name']}: {e}  "
                  f"(files are safe in backup: {item_dir})")

    # ---- Summary ----
    print("\n" + "=" * 55)
    print("SUMMARY")
    print("=" * 55)
    if DRY_RUN:
        print(f"Items scanned:        {len(items)}")
        print(f"Items with no files:  {no_files}")
        print(f"No contract detected: {len(no_contract)}")
    elif BACKUP_ONLY:
        print(f"Backed up:            {len(backed_up)}")
        print(f"Items with no files:  {no_files}")
        print(f"Errors:               {len(errors)}")
    else:
        print(f"Reorged:              {len(reorged)}")
        print(f"Backed up:            {len(backed_up)}")
        print(f"Items with no files:  {no_files}")
        print(f"No contract detected: {len(no_contract)}")
        print(f"Errors:               {len(errors)}")

    if no_contract:
        print("\nNo contract detected (left untouched):")
        for n in no_contract:
            print(f"  - {n}")
    if errors:
        print("\nErrors:")
        for n, e in errors:
            print(f"  - {n}: {e}")
    print(f"\nAll downloaded files are in: {BACKUP_DIR}")
    print("Done.")


if __name__ == "__main__":
    main()
