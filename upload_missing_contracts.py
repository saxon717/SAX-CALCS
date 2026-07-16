"""
upload_missing_contracts.py — Monday-first bulk contract uploader for SAX
=========================================================================
NEW LOGIC (Monday-driven, no re-searching):
  1. Pull ALL Monday items + their attached files in one pass.
  2. Drop any item that already has a contract attached  -> "already has it"
  3. Remaining items = the MISSING list (need a contract).
  4. Match each missing item to a local project folder:
        - primary:  project number (e.g. 26-040)
        - fallback: ~60% fuzzy match on the project name (handles renames)
  5. Find that folder's contract PDF and upload it.

Reuses your existing monday_config.py and config.py — no new settings.

USAGE (from the CALCS folder):
    python upload_missing_contracts.py            # actually uploads
    python upload_missing_contracts.py --dry-run  # shows what WOULD upload

Throwaway utility — delete it when you're done.
"""

import os
import re
import sys
import difflib
import mimetypes
import requests

from monday_config import MONDAY_API_KEY, BOARD_NAME, FILES_COLUMN
from config import (
    BASE_FOLDER,
    YEAR_FOLDER_SUFFIX,
    CONTRACT_SUBFOLDER,
    find_info_file,
    update_info,
)

DRY_RUN = "--dry-run" in sys.argv

MONDAY_API_URL  = "https://api.monday.com/v2"
MONDAY_FILE_URL = "https://api.monday.com/v2/file"
HEADERS = {
    "Authorization": MONDAY_API_KEY,
    "API-Version": "2023-10",
}

CONTRACT_KEYWORDS = ["proposal", "contract", "engineering services"]
PROJECT_NUM_RE    = re.compile(r"(\d{2}-\d{3,})")
NAME_MATCH_CUTOFF = 0.60  # 60% fuzzy match on name


# =========================
# MONDAY HELPERS
# =========================

def monday_query(query, variables=None):
    resp = requests.post(
        MONDAY_API_URL,
        headers=HEADERS,
        json={"query": query, "variables": variables or {}},
    )
    if resp.status_code != 200:
        raise Exception(f"MONDAY API FAILED: {resp.status_code} {resp.text[:200]}")
    data = resp.json()
    if "errors" in data:
        raise Exception(f"MONDAY GRAPHQL ERROR: {data['errors']}")
    return data["data"]


def find_board_and_column():
    boards_data = monday_query("""
    query {
      boards(limit: 100) {
        id name
        columns { id title type }
      }
    }
    """)
    for board in boards_data["boards"]:
        if board["name"].strip().lower() == BOARD_NAME.strip().lower():
            files_col = ""
            for col in board["columns"]:
                if col["title"].strip().lower() == FILES_COLUMN.strip().lower():
                    files_col = col["id"]
            if not files_col:
                raise Exception(f"FILES COLUMN NOT FOUND: {FILES_COLUMN}")
            return board["id"], files_col
    raise Exception(f"MONDAY BOARD NOT FOUND: {BOARD_NAME}")


def fetch_all_items_with_assets(board_id):
    """One pass: every item's id, name, and attached file names."""
    items = []

    def collect(page):
        for it in page["items"]:
            asset_names = [
                (a.get("name") or "").lower()
                for a in (it.get("assets") or [])
            ]
            items.append({
                "id":     it["id"],
                "name":   it["name"],
                "assets": asset_names,
            })

    data = monday_query("""
    query ($board_id: [ID!]) {
      boards(ids: $board_id) {
        items_page(limit: 100) {
          cursor
          items { id name assets { name } }
        }
      }
    }
    """, {"board_id": [board_id]})
    page = data["boards"][0]["items_page"]
    collect(page)
    cursor = page["cursor"]
    while cursor:
        nxt = monday_query("""
        query ($cursor: String!) {
          next_items_page(cursor: $cursor, limit: 100) {
            cursor
            items { id name assets { name } }
          }
        }
        """, {"cursor": cursor})
        page = nxt["next_items_page"]
        collect(page)
        cursor = page["cursor"]
    return items


def item_has_contract(asset_names):
    """True if any attached file looks like a contract."""
    for a in asset_names:
        if a.endswith(".pdf") and any(kw in a for kw in CONTRACT_KEYWORDS):
            return True
    return False


def upload_file(item_id, files_column_id, pdf_path, file_name):
    mime_type = mimetypes.guess_type(pdf_path)[0] or "application/pdf"
    upload_query = (
        f'mutation ($file: File!) {{'
        f'  add_file_to_column('
        f'    item_id: {item_id},'
        f'    column_id: "{files_column_id}",'
        f'    file: $file'
        f'  ) {{ id }}'
        f'}}'
    )
    with open(pdf_path, "rb") as fh:
        resp = requests.post(
            MONDAY_FILE_URL,
            headers={"Authorization": MONDAY_API_KEY},
            data={"query": upload_query},
            files={"variables[file]": (file_name, fh, mime_type)},
        )
    if resp.status_code != 200:
        raise Exception(f"UPLOAD FAILED: {resp.status_code} {resp.text[:200]}")
    data = resp.json()
    if "errors" in data:
        raise Exception(f"UPLOAD ERROR: {data['errors']}")


# =========================
# LOCAL FOLDER HELPERS
# =========================

def build_local_index():
    """
    Return list of dicts: {root, folder, number, name_key}
    name_key = lowercased folder name with the project number stripped off.
    """
    projects = []
    if not os.path.isdir(BASE_FOLDER):
        raise Exception(f"BASE FOLDER NOT FOUND: {BASE_FOLDER}")
    for year_folder in sorted(os.listdir(BASE_FOLDER)):
        if not year_folder.endswith(YEAR_FOLDER_SUFFIX):
            continue
        year_path = os.path.join(BASE_FOLDER, year_folder)
        if not os.path.isdir(year_path):
            continue
        for folder in sorted(os.listdir(year_path)):
            proj_path = os.path.join(year_path, folder)
            if not os.path.isdir(proj_path):
                continue
            m = PROJECT_NUM_RE.search(folder)
            number = m.group(1) if m else ""
            name_key = folder.lower()
            if number:
                name_key = name_key.replace(number.lower(), "")
            name_key = name_key.strip().lstrip("-").strip()
            projects.append({
                "root":   proj_path,
                "folder": folder,
                "number": number,
                "name_key": name_key,
            })
    return projects


def match_folder(item_name, local_index, num_index):
    """Match a Monday item to a local project. Returns dict or None."""
    m = PROJECT_NUM_RE.search(item_name)
    number = m.group(1) if m else ""

    # 1) exact project-number match
    if number and number in num_index:
        return num_index[number]

    # 2) fuzzy name match (~60%)
    item_key = item_name.lower()
    if number:
        item_key = item_key.replace(number.lower(), "")
    item_key = item_key.strip().lstrip("-").strip()
    if not item_key:
        return None

    best, best_ratio = None, 0.0
    for p in local_index:
        if not p["name_key"]:
            continue
        r = difflib.SequenceMatcher(None, item_key, p["name_key"]).ratio()
        if r > best_ratio:
            best, best_ratio = p, r
    if best and best_ratio >= NAME_MATCH_CUTOFF:
        return best
    return None


def find_contract_pdf(project_root):
    """Return (pdf_path, file_name) for the best contract PDF, or (None, None)."""
    contract_folder = os.path.join(project_root, CONTRACT_SUBFOLDER)
    if not os.path.isdir(contract_folder):
        return None, None
    pdfs = [
        os.path.join(contract_folder, f)
        for f in os.listdir(contract_folder)
        if f.lower().endswith(".pdf") and not f.startswith("~")
    ]
    if not pdfs:
        return None, None
    preferred = [
        p for p in pdfs
        if any(kw in os.path.basename(p).lower() for kw in CONTRACT_KEYWORDS)
    ]
    if preferred:
        pdfs = preferred
    best = max(pdfs, key=os.path.getmtime)
    return best, os.path.basename(best)


# =========================
# MAIN
# =========================

def main():
    mode = "DRY RUN (no uploads)" if DRY_RUN else "LIVE (will upload)"
    print(f"=== UPLOAD MISSING CONTRACTS — {mode} ===\n")

    # --- Step 1: Monday scan (once) ---
    print("Connecting to Monday...")
    board_id, files_column_id = find_board_and_column()
    print("Fetching all Monday items + files...")
    all_items = fetch_all_items_with_assets(board_id)
    print(f"  {len(all_items)} items on board '{BOARD_NAME}'")

    # --- Step 2/3: build the MISSING list ---
    missing = [it for it in all_items if not item_has_contract(it["assets"])]
    has_it  = len(all_items) - len(missing)
    print(f"  {has_it} already have a contract")
    print(f"  {len(missing)} missing a contract\n")

    # --- Step 4: local index for matching ---
    local_index = build_local_index()
    num_index   = {p["number"]: p for p in local_index if p["number"]}

    uploaded    = []
    no_folder   = []
    no_contract = []
    errors      = []

    for it in missing:
        proj = match_folder(it["name"], local_index, num_index)
        if not proj:
            no_folder.append(it["name"])
            print(f"[NO FOLDER]     {it['name']}")
            continue

        pdf_path, file_name = find_contract_pdf(proj["root"])
        if not pdf_path:
            no_contract.append(f"{it['name']}  ->  {proj['folder']}")
            print(f"[NO CONTRACT]   {it['name']}  (folder: {proj['folder']})")
            continue

        try:
            if DRY_RUN:
                print(f"[WOULD UPLOAD]  {it['name']}  <-  {file_name}")
                uploaded.append(it["name"])
                continue

            upload_file(it["id"], files_column_id, pdf_path, file_name)
            print(f"[UPLOADED]      {it['name']}  <-  {file_name}")
            uploaded.append(it["name"])

            # best-effort INFO flag
            if proj["number"]:
                try:
                    info_path = find_info_file(proj["root"], proj["number"])
                    if info_path:
                        update_info(info_path, proj["root"], {"MONDAY_UPLOADED": "Y"})
                except Exception:
                    pass

        except Exception as e:
            errors.append((it["name"], str(e)))
            print(f"[ERROR]         {it['name']}: {e}")

    # --- Summary ---
    print("\n" + "=" * 55)
    print("SUMMARY")
    print("=" * 55)
    verb = "Would upload" if DRY_RUN else "Uploaded"
    print(f"{verb}:                {len(uploaded)}")
    print(f"Already had contract:   {has_it}")
    print(f"No folder match:        {len(no_folder)}")
    print(f"Folder found, no PDF:   {len(no_contract)}")
    print(f"Errors:                 {len(errors)}")

    if no_folder:
        print("\nMonday items with NO folder match:")
        for n in no_folder:
            print(f"  - {n}")
    if no_contract:
        print("\nMatched a folder but found NO contract PDF:")
        for n in no_contract:
            print(f"  - {n}")
    if errors:
        print("\nErrors:")
        for n, e in errors:
            print(f"  - {n}: {e}")
    print("\nDone.")


if __name__ == "__main__":
    main()
