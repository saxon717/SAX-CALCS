"""
bulk_upload_contracts.py — one-shot bulk contract uploader for SAX
==================================================================
Scans EVERY project folder under BASE_FOLDER, finds each project's
contract PDF, checks Monday for that project, and uploads the contract
if it isn't already attached to the project's Files column.

Reuses your existing monday_config.py and config.py — no new settings.

USAGE (from the CALCS folder):
    python bulk_upload_contracts.py            # actually uploads
    python bulk_upload_contracts.py --dry-run  # shows what WOULD upload, no changes

This is a throwaway utility — delete it whenever you're done.
"""

import os
import re
import sys
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
PROJECT_NUM_RE = re.compile(r"^(\d{2}-\d{3,})")


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


def fetch_all_items(board_id):
    """Return list of {id, name} for every item on the board."""
    items = []
    data = monday_query("""
    query ($board_id: [ID!]) {
      boards(ids: $board_id) {
        items_page(limit: 500) {
          cursor
          items { id name }
        }
      }
    }
    """, {"board_id": [board_id]})
    page = data["boards"][0]["items_page"]
    items.extend(page["items"])
    cursor = page["cursor"]
    while cursor:
        nxt = monday_query("""
        query ($cursor: String!) {
          next_items_page(cursor: $cursor, limit: 500) {
            cursor
            items { id name }
          }
        }
        """, {"cursor": cursor})
        page = nxt["next_items_page"]
        items.extend(page["items"])
        cursor = page["cursor"]
    return items


def get_item_assets(item_id):
    data = monday_query(f"""
    query {{
      items(ids: [{item_id}]) {{
        assets {{ name }}
      }}
    }}
    """)
    names = []
    for item in (data.get("items") or []):
        for asset in item.get("assets", []):
            names.append((asset.get("name") or "").lower())
    return names


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


def iter_projects():
    """Yield (project_root, folder_name) for every project folder."""
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
            if os.path.isdir(proj_path):
                yield proj_path, folder


# =========================
# MAIN
# =========================

def main():
    mode = "DRY RUN (no uploads)" if DRY_RUN else "LIVE (will upload)"
    print(f"=== BULK CONTRACT UPLOAD — {mode} ===\n")

    print("Connecting to Monday...")
    board_id, files_column_id = find_board_and_column()
    print("Fetching all Monday items...")
    all_items = fetch_all_items(board_id)
    name_to_id = {it["name"].strip().lower(): it["id"] for it in all_items}
    print(f"  {len(all_items)} items on board '{BOARD_NAME}'\n")

    uploaded    = []
    already     = []
    no_contract = []
    no_item     = []
    errors      = []

    for project_root, folder_name in iter_projects():
        pdf_path, file_name = find_contract_pdf(project_root)
        if not pdf_path:
            no_contract.append(folder_name)
            continue

        item_id = name_to_id.get(folder_name.strip().lower())
        if not item_id:
            no_item.append(folder_name)
            print(f"[NO MONDAY ITEM] {folder_name}")
            continue

        try:
            existing = get_item_assets(item_id)
            fn_lower = file_name.lower()
            on_monday = any(fn_lower in e or e in fn_lower for e in existing)

            if on_monday:
                already.append(folder_name)
                print(f"[ALREADY UP]    {folder_name}  ({file_name})")
                continue

            if DRY_RUN:
                print(f"[WOULD UPLOAD]  {folder_name}  ({file_name})")
                uploaded.append(folder_name)
                continue

            upload_file(item_id, files_column_id, pdf_path, file_name)
            print(f"[UPLOADED]      {folder_name}  ({file_name})")
            uploaded.append(folder_name)

            # Best-effort: mark INFO file so the UI knows it's done
            m = PROJECT_NUM_RE.match(folder_name)
            if m:
                try:
                    info_path = find_info_file(project_root, m.group(1))
                    if info_path:
                        update_info(info_path, project_root, {"MONDAY_UPLOADED": "Y"})
                except Exception:
                    pass

        except Exception as e:
            errors.append((folder_name, str(e)))
            print(f"[ERROR]         {folder_name}: {e}")

    # =========================
    # SUMMARY
    # =========================
    print("\n" + "=" * 55)
    print("SUMMARY")
    print("=" * 55)
    verb = "Would upload" if DRY_RUN else "Uploaded"
    print(f"{verb}:              {len(uploaded)}")
    print(f"Already on Monday:    {len(already)}")
    print(f"No contract PDF:      {len(no_contract)}")
    print(f"No matching item:     {len(no_item)}")
    print(f"Errors:               {len(errors)}")

    if no_item:
        print("\nProjects with a contract but NO Monday item (skipped):")
        for n in no_item:
            print(f"  - {n}")
    if errors:
        print("\nErrors:")
        for n, e in errors:
            print(f"  - {n}: {e}")
    print("\nDone.")


if __name__ == "__main__":
    main()