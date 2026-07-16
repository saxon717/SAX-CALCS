"""
check_missing_locations.py — report which Monday items have NO Location
=======================================================================
Read-only. Makes no changes. Just scans the board and lists which items
are missing a Location value.

USAGE (from the CALCS folder):
    python check_missing_locations.py

Throwaway utility — delete it when you're done.
"""

import sys
import requests

from monday_config import MONDAY_API_KEY, BOARD_NAME

LOCATION_COLUMN_TITLE = "Location"   # change if your column is named differently

MONDAY_API_URL = "https://api.monday.com/v2"
HEADERS = {"Authorization": MONDAY_API_KEY, "API-Version": "2023-10"}


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


def find_board_and_column():
    data = monday_query("""
    query { boards(limit: 100) { id name columns { id title } } }
    """)
    for board in data["boards"]:
        if board["name"].strip().lower() == BOARD_NAME.strip().lower():
            for col in board["columns"]:
                if col["title"].strip().lower() == LOCATION_COLUMN_TITLE.strip().lower():
                    return board["id"], col["id"]
            titles = ", ".join(c["title"] for c in board["columns"])
            raise Exception(f"'{LOCATION_COLUMN_TITLE}' COLUMN NOT FOUND. Columns: {titles}")
    raise Exception(f"MONDAY BOARD NOT FOUND: {BOARD_NAME}")


def fetch_all_items(board_id, col_id):
    items = []

    def collect(page):
        for it in page["items"]:
            val = ""
            for cv in (it.get("column_values") or []):
                if cv["id"] == col_id:
                    val = (cv.get("text") or "").strip()
            items.append({"name": it["name"], "location": val})

    data = monday_query("""
    query ($board_id: [ID!], $cols: [String!]) {
      boards(ids: $board_id) {
        items_page(limit: 100) {
          cursor items { name column_values(ids: $cols) { id text } }
        }
      }
    }
    """, {"board_id": [board_id], "cols": [col_id]})
    page = data["boards"][0]["items_page"]
    collect(page)
    cursor = page["cursor"]
    while cursor:
        nxt = monday_query("""
        query ($cursor: String!, $cols: [String!]) {
          next_items_page(cursor: $cursor, limit: 100) {
            cursor items { name column_values(ids: $cols) { id text } }
          }
        }
        """, {"cursor": cursor, "cols": [col_id]})
        page = nxt["next_items_page"]
        collect(page)
        cursor = page["cursor"]
    return items


def main():
    print(f"=== CHECK MONDAY LOCATIONS — board '{BOARD_NAME}' ===\n")
    board_id, col_id = find_board_and_column()
    items = fetch_all_items(board_id, col_id)

    missing = [it for it in items if not it["location"]]
    have    = [it for it in items if it["location"]]

    print(f"Total items:        {len(items)}")
    print(f"Have a location:    {len(have)}")
    print(f"MISSING a location: {len(missing)}\n")

    if missing:
        print("MISSING LOCATION:")
        for it in sorted(missing, key=lambda x: x["name"].lower()):
            print(f"  - {it['name']}")
    else:
        print("All items have a location.")

    print("\nDone.")


if __name__ == "__main__":
    main()
