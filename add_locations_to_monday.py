"""
add_locations_to_monday.py — fill the Location column on Monday for SAX
=======================================================================
LOGIC:
  1. Find all items on the Monday board.
  2. Match each item to its local project folder (project number, ~60% name fallback).
  3. Get the project location:
        - primary:  the project's INFO file (already parsed from the contract)
        - fallback: parse the contract PDF directly (same "RE:" logic as 01_info.py)
  4. Write that location into the Monday "Location" column.

Handles BOTH kinds of Location column automatically:
   - plain TEXT column        -> writes the address string
   - Monday map LOCATION type -> geocodes the address (OpenStreetMap) and writes lat/lng

By default it SKIPS items that already have a Location filled in.

Reuses your existing monday_config.py and config.py.

USAGE (from the CALCS folder):
    python add_locations_to_monday.py --dry-run   # preview, no changes
    python add_locations_to_monday.py             # write locations
    python add_locations_to_monday.py --overwrite # also overwrite items that already have one

Throwaway utility — delete it when you're done.
"""

import os
import re
import sys
import json
import time
import difflib
import requests

from monday_config import MONDAY_API_KEY, BOARD_NAME
from config import (
    BASE_FOLDER,
    YEAR_FOLDER_SUFFIX,
    CONTRACT_SUBFOLDER,
    read_info,
)

DRY_RUN   = "--dry-run" in sys.argv
OVERWRITE = "--overwrite" in sys.argv

LOCATION_COLUMN_TITLE = "Location"   # change here if your column is named differently

MONDAY_API_URL = "https://api.monday.com/v2"
HEADERS = {
    "Authorization": MONDAY_API_KEY,
    "API-Version": "2023-10",
}

PROJECT_NUM_RE    = re.compile(r"(\d{2}-\d{3,})")
NAME_MATCH_CUTOFF = 0.60


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


def find_board_and_location_column():
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
            for col in board["columns"]:
                if col["title"].strip().lower() == LOCATION_COLUMN_TITLE.strip().lower():
                    return board["id"], col["id"], col["type"]
            titles = ", ".join(c["title"] for c in board["columns"])
            raise Exception(
                f"'{LOCATION_COLUMN_TITLE}' COLUMN NOT FOUND. Columns are: {titles}"
            )
    raise Exception(f"MONDAY BOARD NOT FOUND: {BOARD_NAME}")


def fetch_all_items(board_id, location_col_id):
    """One pass: id, name, and current value of the location column."""
    items = []

    def collect(page):
        for it in page["items"]:
            current = ""
            for cv in (it.get("column_values") or []):
                if cv["id"] == location_col_id:
                    current = (cv.get("text") or "").strip()
            items.append({"id": it["id"], "name": it["name"], "current": current})

    q_first = """
    query ($board_id: [ID!], $cols: [String!]) {
      boards(ids: $board_id) {
        items_page(limit: 100) {
          cursor
          items { id name column_values(ids: $cols) { id text } }
        }
      }
    }
    """
    data = monday_query(q_first, {"board_id": [board_id], "cols": [location_col_id]})
    page = data["boards"][0]["items_page"]
    collect(page)
    cursor = page["cursor"]
    while cursor:
        q_next = """
        query ($cursor: String!, $cols: [String!]) {
          next_items_page(cursor: $cursor, limit: 100) {
            cursor
            items { id name column_values(ids: $cols) { id text } }
          }
        }
        """
        nxt = monday_query(q_next, {"cursor": cursor, "cols": [location_col_id]})
        page = nxt["next_items_page"]
        collect(page)
        cursor = page["cursor"]
    return items


def set_text_value(board_id, item_id, col_id, text_value):
    monday_query("""
    mutation ($board_id: ID!, $item_id: ID!, $col_id: String!, $val: String!) {
      change_simple_column_value(
        board_id: $board_id, item_id: $item_id, column_id: $col_id, value: $val
      ) { id }
    }
    """, {"board_id": board_id, "item_id": item_id, "col_id": col_id, "val": text_value})


def set_location_value(board_id, item_id, col_id, lat, lng, address):
    val = json.dumps({"lat": str(lat), "lng": str(lng), "address": address})
    monday_query("""
    mutation ($board_id: ID!, $item_id: ID!, $col_id: String!, $val: JSON!) {
      change_column_value(
        board_id: $board_id, item_id: $item_id, column_id: $col_id, value: $val
      ) { id }
    }
    """, {"board_id": board_id, "item_id": item_id, "col_id": col_id, "val": val})


def geocode(address):
    """Return (lat, lng) via OpenStreetMap Nominatim, or (None, None)."""
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "json", "limit": 1},
            headers={"User-Agent": "sax-monday-location/1.0"},
            timeout=20,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data:
                return data[0]["lat"], data[0]["lon"]
    except Exception:
        pass
    return None, None


# =========================
# LOCAL FOLDER + ADDRESS
# =========================

def build_local_index():
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
                "root": proj_path, "folder": folder,
                "number": number, "name_key": name_key,
            })
    return projects


def match_folder(item_name, local_index, num_index):
    m = PROJECT_NUM_RE.search(item_name)
    number = m.group(1) if m else ""
    if number and number in num_index:
        return num_index[number]
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


def address_from_info(project_root, project_number):
    """Build a full address string from the project's INFO file, or ''."""
    try:
        info, path = read_info(project_root, project_number)
    except Exception:
        return ""
    if not path:
        return ""
    verified = info.get("VERIFIED_PROJECT_ADDRESS", "").strip()
    if verified:
        return verified
    street = info.get("PROJECT_ADDRESS", "").strip() or info.get("MANUAL_PROJECT_ADDRESS", "").strip()
    if not street:
        return ""
    city  = info.get("CITY", "").strip()
    state = info.get("STATE", "").strip()
    zc    = info.get("ZIP_CODE", "").strip()
    parts = [street]
    if city:
        parts.append(city)
    tail = " ".join(x for x in [state, zc] if x)
    if tail:
        parts.append(tail)
    return ", ".join(parts)


def address_from_contract(project_root):
    """Parse the contract PDF directly (same RE: logic as 01_info.py)."""
    try:
        import pdfplumber
    except ImportError:
        return ""
    contract_folder = os.path.join(project_root, CONTRACT_SUBFOLDER)
    if not os.path.isdir(contract_folder):
        return ""
    pdf_path = ""
    for f in os.listdir(contract_folder):
        if f.lower().endswith(".pdf") and not f.startswith("~"):
            pdf_path = os.path.join(contract_folder, f)
            break
    if not pdf_path:
        return ""
    try:
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                ex = page.extract_text()
                if ex:
                    text += ex + "\n"
    except Exception:
        return ""
    text  = re.sub(r"\(cid:\d+\)", "", text)
    lines = text.split("\n")
    lower = [l.lower().strip() for l in lines]
    for i, line in enumerate(lower):
        if "re:" in line:
            for j in range(i, min(i + 10, len(lines))):
                cand = lines[j].strip()
                if any(c.isdigit() for c in cand) and "," in cand:
                    return re.sub(r"\s+", " ", cand).strip()
    return ""


# =========================
# MAIN
# =========================

def main():
    mode = "DRY RUN (no changes)" if DRY_RUN else "LIVE (will write)"
    print(f"=== ADD LOCATIONS TO MONDAY — {mode} ===\n")

    print("Connecting to Monday...")
    board_id, loc_col_id, loc_col_type = find_board_and_location_column()
    is_map = loc_col_type == "location"
    print(f"  Location column type: {loc_col_type}"
          f"{'  (map type — will geocode)' if is_map else '  (text)'}")

    print("Fetching all Monday items...")
    all_items = fetch_all_items(board_id, loc_col_id)
    print(f"  {len(all_items)} items on board '{BOARD_NAME}'\n")

    local_index = build_local_index()
    num_index   = {p["number"]: p for p in local_index if p["number"]}

    updated     = []
    skipped_has = []
    no_folder   = []
    no_address  = []
    no_geo      = []
    errors      = []

    for it in all_items:
        if it["current"] and not OVERWRITE:
            skipped_has.append(it["name"])
            continue

        proj = match_folder(it["name"], local_index, num_index)
        if not proj:
            no_folder.append(it["name"])
            print(f"[NO FOLDER]    {it['name']}")
            continue

        address = address_from_info(proj["root"], proj["number"])
        if not address:
            address = address_from_contract(proj["root"])
        if not address:
            no_address.append(f"{it['name']}  ->  {proj['folder']}")
            print(f"[NO ADDRESS]   {it['name']}  (folder: {proj['folder']})")
            continue

        try:
            if is_map:
                lat, lng = geocode(address)
                time.sleep(1)  # Nominatim rate limit
                if not lat:
                    no_geo.append(f"{it['name']}  ({address})")
                    print(f"[NO GEOCODE]   {it['name']}  ({address})")
                    continue
                if DRY_RUN:
                    print(f"[WOULD SET]    {it['name']}  ->  {address}  ({lat},{lng})")
                else:
                    set_location_value(board_id, it["id"], loc_col_id, lat, lng, address)
                    print(f"[SET]          {it['name']}  ->  {address}")
            else:
                if DRY_RUN:
                    print(f"[WOULD SET]    {it['name']}  ->  {address}")
                else:
                    set_text_value(board_id, it["id"], loc_col_id, address)
                    print(f"[SET]          {it['name']}  ->  {address}")
            updated.append(it["name"])
        except Exception as e:
            errors.append((it["name"], str(e)))
            print(f"[ERROR]        {it['name']}: {e}")

    # --- Summary ---
    print("\n" + "=" * 55)
    print("SUMMARY")
    print("=" * 55)
    verb = "Would set" if DRY_RUN else "Set"
    print(f"{verb}:                    {len(updated)}")
    print(f"Already had location:     {len(skipped_has)}")
    print(f"No folder match:          {len(no_folder)}")
    print(f"No address found:         {len(no_address)}")
    if is_map:
        print(f"Could not geocode:        {len(no_geo)}")
    print(f"Errors:                   {len(errors)}")

    if no_folder:
        print("\nMonday items with NO folder match:")
        for n in no_folder:
            print(f"  - {n}")
    if no_address:
        print("\nMatched a folder but found NO address:")
        for n in no_address:
            print(f"  - {n}")
    if no_geo:
        print("\nCould not geocode (map column only):")
        for n in no_geo:
            print(f"  - {n}")
    if errors:
        print("\nErrors:")
        for n, e in errors:
            print(f"  - {n}: {e}")
    print("\nDone.")


if __name__ == "__main__":
    main()
