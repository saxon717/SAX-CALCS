"""
fix_geocodes.py — geocode the items that already have an address
================================================================
Targets ONLY Monday items that:
  - have a blank Location column, AND
  - already have an address in their INFO file
(i.e. the "HAS ADDRESS (geocode likely failed)" bucket from the diagnosis).

Stronger geocoding than the original script:
  - cleans the address (drops Suite/Unit/#, stray APN text, extra spaces)
  - tries several forms (full -> street+city+state -> city+state+zip)
  - US Census geocoder first (best for US street addresses), then OpenStreetMap
  - writes lat/lng to the Location column

USAGE (from the CALCS folder):
    python fix_geocodes.py --dry-run   # show what it resolves, no writes
    python fix_geocodes.py             # write locations to Monday

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
from config import BASE_FOLDER, YEAR_FOLDER_SUFFIX, read_info

DRY_RUN = "--dry-run" in sys.argv

LOCATION_COLUMN_TITLE = "Location"

MONDAY_API_URL = "https://api.monday.com/v2"
HEADERS = {"Authorization": MONDAY_API_KEY, "API-Version": "2023-10"}
PROJECT_NUM_RE    = re.compile(r"(\d{2}-\d{3,})")
NAME_MATCH_CUTOFF = 0.60


# =========================
# MONDAY
# =========================

def monday_query(query, variables=None):
    resp = requests.post(MONDAY_API_URL, headers=HEADERS,
                         json={"query": query, "variables": variables or {}})
    if resp.status_code != 200:
        raise Exception(f"MONDAY API FAILED: {resp.status_code} {resp.text[:200]}")
    data = resp.json()
    if "errors" in data:
        raise Exception(f"MONDAY GRAPHQL ERROR: {data['errors']}")
    return data["data"]


def find_board_and_column():
    data = monday_query("query { boards(limit:100){ id name columns{ id title type } } }")
    for b in data["boards"]:
        if b["name"].strip().lower() == BOARD_NAME.strip().lower():
            for c in b["columns"]:
                if c["title"].strip().lower() == LOCATION_COLUMN_TITLE.strip().lower():
                    return b["id"], c["id"], c["type"]
            raise Exception(f"'{LOCATION_COLUMN_TITLE}' column not found")
    raise Exception(f"MONDAY BOARD NOT FOUND: {BOARD_NAME}")


def fetch_all_items(board_id, loc_col):
    items = []

    def collect(page):
        for it in page["items"]:
            cur = ""
            for cv in (it.get("column_values") or []):
                if cv["id"] == loc_col:
                    cur = (cv.get("text") or "").strip()
            items.append({"id": it["id"], "name": it["name"], "current": cur})

    data = monday_query("""
    query ($board_id:[ID!], $cols:[String!]) {
      boards(ids:$board_id){ items_page(limit:100){ cursor
        items{ id name column_values(ids:$cols){ id text } } } }
    }""", {"board_id": [board_id], "cols": [loc_col]})
    page = data["boards"][0]["items_page"]
    collect(page)
    cursor = page["cursor"]
    while cursor:
        nxt = monday_query("""
        query ($cursor:String!, $cols:[String!]) {
          next_items_page(cursor:$cursor, limit:100){ cursor
            items{ id name column_values(ids:$cols){ id text } } }
        }""", {"cursor": cursor, "cols": [loc_col]})
        page = nxt["next_items_page"]
        collect(page)
        cursor = page["cursor"]
    return items


def set_location(board_id, item_id, col_id, lat, lng, address):
    val = json.dumps({"lat": str(lat), "lng": str(lng), "address": address})
    monday_query("""
    mutation ($board_id:ID!, $item_id:ID!, $col_id:String!, $val:JSON!) {
      change_column_value(board_id:$board_id, item_id:$item_id,
                          column_id:$col_id, value:$val){ id }
    }""", {"board_id": board_id, "item_id": item_id, "col_id": col_id, "val": val})


def set_text(board_id, item_id, col_id, text):
    monday_query("""
    mutation ($board_id:ID!, $item_id:ID!, $col_id:String!, $val:String!) {
      change_simple_column_value(board_id:$board_id, item_id:$item_id,
                                 column_id:$col_id, value:$val){ id }
    }""", {"board_id": board_id, "item_id": item_id, "col_id": col_id, "val": text})


# =========================
# GEOCODING
# =========================

def clean_part(s):
    s = re.sub(r'(?i)\b(suite|ste|unit|apt|#)\s*\S+', '', s)
    s = re.sub(r'(?i)\bapn\b.*', '', s)
    s = re.sub(r'\s+', ' ', s).strip().strip(',').strip()
    return s


def geocode_census(one_line):
    try:
        r = requests.get(
            "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress",
            params={"address": one_line, "benchmark": "Public_AR_Current", "format": "json"},
            timeout=25,
        )
        if r.status_code == 200:
            matches = r.json().get("result", {}).get("addressMatches", [])
            if matches:
                c = matches[0]["coordinates"]
                return c["y"], c["x"]  # lat, lng
    except Exception:
        pass
    return None, None


def geocode_osm(one_line):
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": one_line, "format": "json", "limit": 1, "countrycodes": "us"},
            headers={"User-Agent": "sax-geocode-fix/1.0"},
            timeout=25,
        )
        if r.status_code == 200:
            data = r.json()
            if data:
                return data[0]["lat"], data[0]["lon"]
    except Exception:
        pass
    return None, None


def geocode(street, city, state, zc):
    street = clean_part(street)
    city   = clean_part(city)
    tail   = " ".join(x for x in [state, zc] if x)
    forms = []
    if street and city and tail:
        forms.append(f"{street}, {city}, {tail}")
    if street and city and state:
        forms.append(f"{street}, {city}, {state}")
    if city and tail:
        forms.append(f"{city}, {tail}")
    if street and state:
        forms.append(f"{street}, {state}")
    seen = set()
    for form in forms:
        if form in seen:
            continue
        seen.add(form)
        lat, lng = geocode_census(form)
        if lat:
            return lat, lng, form
        lat, lng = geocode_osm(form)
        time.sleep(1)  # OSM rate limit
        if lat:
            return lat, lng, form
    return None, None, ""


# =========================
# LOCAL MATCHING + INFO
# =========================

def build_local_index():
    projects = []
    for yf in sorted(os.listdir(BASE_FOLDER)):
        if not yf.endswith(YEAR_FOLDER_SUFFIX):
            continue
        yp = os.path.join(BASE_FOLDER, yf)
        if not os.path.isdir(yp):
            continue
        for folder in sorted(os.listdir(yp)):
            pp = os.path.join(yp, folder)
            if not os.path.isdir(pp):
                continue
            m = PROJECT_NUM_RE.search(folder)
            number = m.group(1) if m else ""
            nk = folder.lower()
            if number:
                nk = nk.replace(number.lower(), "")
            nk = nk.strip().lstrip("-").strip()
            projects.append({"root": pp, "folder": folder, "number": number, "name_key": nk})
    return projects


def match_folder(item_name, local_index, num_index):
    m = PROJECT_NUM_RE.search(item_name)
    number = m.group(1) if m else ""
    if number and number in num_index:
        return num_index[number]
    ik = item_name.lower()
    if number:
        ik = ik.replace(number.lower(), "")
    ik = ik.strip().lstrip("-").strip()
    if not ik:
        return None
    best, ratio = None, 0.0
    for p in local_index:
        if not p["name_key"]:
            continue
        r = difflib.SequenceMatcher(None, ik, p["name_key"]).ratio()
        if r > ratio:
            best, ratio = p, r
    return best if best and ratio >= NAME_MATCH_CUTOFF else None


def address_parts(project_root, project_number):
    try:
        info, path = read_info(project_root, project_number)
    except Exception:
        return None
    if not path:
        return None
    street = info.get("PROJECT_ADDRESS", "").strip() or info.get("MANUAL_PROJECT_ADDRESS", "").strip()
    verified = info.get("VERIFIED_PROJECT_ADDRESS", "").strip()
    if verified and not street:
        street = verified
    if not street:
        return None
    return (street, info.get("CITY", "").strip(),
            info.get("STATE", "").strip(), info.get("ZIP_CODE", "").strip())


# =========================
# MAIN
# =========================

def main():
    mode = "DRY RUN (no writes)" if DRY_RUN else "LIVE (writing locations)"
    print(f"=== FIX GEOCODES — {mode} ===\n")

    board_id, loc_col, loc_type = find_board_and_column()
    is_map = loc_type == "location"
    print(f"Location column type: {loc_type}")
    items = fetch_all_items(board_id, loc_col)
    print(f"{len(items)} items on board '{BOARD_NAME}'\n")

    local_index = build_local_index()
    num_index = {p["number"]: p for p in local_index if p["number"]}

    fixed, still_failing, skipped = [], [], 0

    for it in items:
        if it["current"]:
            continue
        proj = match_folder(it["name"], local_index, num_index)
        if not proj:
            continue
        parts = address_parts(proj["root"], proj["number"])
        if not parts:
            continue  # no address -> not this bucket
        skipped += 0
        street, city, state, zc = parts

        lat, lng, used = geocode(street, city, state, zc)
        if not lat:
            still_failing.append((it["name"], f"{street}, {city}, {state} {zc}".strip()))
            print(f"[STILL FAILS] {it['name']}  ({street}, {city}, {state} {zc})")
            continue

        full = f"{street}, {city}, {state} {zc}".strip().strip(",")
        if DRY_RUN:
            print(f"[WOULD SET]   {it['name']}  ->  {used}  ({lat},{lng})")
        else:
            if is_map:
                set_location(board_id, it["id"], loc_col, lat, lng, full)
            else:
                set_text(board_id, it["id"], loc_col, full)
            print(f"[SET]         {it['name']}  ->  {full}")
        fixed.append(it["name"])

    print("\n" + "=" * 55)
    print("SUMMARY")
    print("=" * 55)
    verb = "Would fix" if DRY_RUN else "Fixed"
    print(f"{verb}:            {len(fixed)}")
    print(f"Still failing:    {len(still_failing)}")
    if still_failing:
        print("\nStill couldn't geocode:")
        for n, a in still_failing:
            print(f"  - {n}  ({a})")
    print("\nDone.")


if __name__ == "__main__":
    main()
