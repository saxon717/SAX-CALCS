import os
import sys
import json
import mimetypes
import requests

from monday_config import (
    MONDAY_API_KEY,
    BOARD_NAME,
    FILES_COLUMN
)

# =========================
# SETTINGS
# =========================

CONFIRM_BEFORE_UPLOAD = True

MONDAY_API_URL = "https://api.monday.com/v2"
MONDAY_FILE_URL = "https://api.monday.com/v2/file"

HEADERS = {
    "Authorization": MONDAY_API_KEY,
    "API-Version": "2023-10"
}

# =========================
# BASE FOLDER
# =========================

base_folder = (
    r"C:\Users\saxon\Dropbox\SHEAR FORCE"
    r"\1) CURRENT PROJECTS"
)

# =========================
# PROJECT NUMBER
# =========================

project_number = sys.argv[1]
year_prefix = project_number[:2]

# =========================
# FIND YEAR FOLDER
# =========================

year_folder = os.path.join(
    base_folder,
    f"{year_prefix}-XXX"
)

if not os.path.exists(year_folder):
    raise Exception(f"YEAR FOLDER NOT FOUND: {year_folder}")

# =========================
# FIND PROJECT FOLDER
# =========================

project_root = ""
project_folder_name = ""

for folder in os.listdir(year_folder):
    if folder.startswith(project_number):
        project_root = os.path.join(year_folder, folder)
        project_folder_name = folder
        break

if project_root == "":
    raise Exception(f"PROJECT FOLDER NOT FOUND FOR: {project_number}")

print("\nMONDAY CONTRACT UPLOAD")
print(project_folder_name)

# =========================
# FIND CONTRACT FOLDER
# =========================

contract_folder = os.path.join(project_root, "CONTRACT")

if not os.path.exists(contract_folder):
    raise Exception(f"CONTRACT FOLDER NOT FOUND: {contract_folder}")

# =========================
# FIND CONTRACT PDF
# =========================

contract_pdfs = []

for file in os.listdir(contract_folder):
    if file.lower().endswith(".pdf"):
        contract_pdfs.append(os.path.join(contract_folder, file))

if len(contract_pdfs) == 0:
    raise Exception("NO CONTRACT PDF FOUND")

preferred_pdfs = [
    pdf for pdf in contract_pdfs
    if any(
        keyword in os.path.basename(pdf).lower()
        for keyword in ["proposal", "contract", "engineering services"]
    )
]

if len(preferred_pdfs) > 0:
    contract_pdfs = preferred_pdfs

contract_pdf = max(contract_pdfs, key=os.path.getmtime)
contract_file_name = os.path.basename(contract_pdf)

print("\nCONTRACT PDF FOUND")
print(contract_file_name)

# =========================
# MONDAY GRAPHQL HELPER
# =========================

def monday_query(query, variables=None):

    response = requests.post(
        MONDAY_API_URL,
        headers=HEADERS,
        json={
            "query": query,
            "variables": variables or {}
        }
    )

    if response.status_code != 200:
        print(f"STATUS: {response.status_code}")
        print(f"RESPONSE: {response.text}")
        raise Exception("MONDAY API REQUEST FAILED")

    data = response.json()

    if "errors" in data:
        print(json.dumps(data["errors"], indent=2))
        raise Exception("MONDAY GRAPHQL ERROR")

    return data["data"]

# =========================
# FIND BOARD + FILES COLUMN
# =========================

boards_query = """
query {
  boards(limit: 100) {
    id
    name
    columns {
      id
      title
      type
    }
  }
}
"""

boards_data = monday_query(boards_query)

board_id = ""
files_column_id = ""

for board in boards_data["boards"]:
    if board["name"].strip().lower() == BOARD_NAME.strip().lower():
        board_id = board["id"]
        for column in board["columns"]:
            if column["title"].strip().lower() == FILES_COLUMN.strip().lower():
                files_column_id = column["id"]
        break

if board_id == "":
    raise Exception(f"MONDAY BOARD NOT FOUND: {BOARD_NAME}")

print("\nMONDAY BOARD FOUND")

if files_column_id == "":
    raise Exception(f"FILES COLUMN NOT FOUND: {FILES_COLUMN}")

print("\nFILES COLUMN FOUND")

# =========================
# FIND MONDAY ITEM
# =========================

def fetch_all_items(board_id):

    items = []

    items_query = """
    query ($board_id: [ID!]) {
      boards(ids: $board_id) {
        items_page(limit: 500) {
          cursor
          items {
            id
            name
          }
        }
      }
    }
    """

    data = monday_query(items_query, {"board_id": [board_id]})
    page = data["boards"][0]["items_page"]
    items.extend(page["items"])
    cursor = page["cursor"]

    while cursor:

        next_query = """
        query ($cursor: String!) {
          next_items_page(cursor: $cursor, limit: 500) {
            cursor
            items {
              id
              name
            }
          }
        }
        """

        next_data = monday_query(next_query, {"cursor": cursor})
        next_page = next_data["next_items_page"]
        items.extend(next_page["items"])
        cursor = next_page["cursor"]

    return items

all_items = fetch_all_items(board_id)

item_id = ""

# exact match first
for item in all_items:
    if item["name"].strip().lower() == project_folder_name.strip().lower():
        item_id = item["id"]
        break

# fallback: match by project number
if item_id == "":

    close_matches = [
        item for item in all_items
        if project_number.lower() in item["name"].strip().lower()
    ]

    if len(close_matches) == 0:
        raise Exception(
            f"MONDAY ITEM NOT FOUND — NO CLOSE MATCHES FOR: {project_number}"
        )

    for match in close_matches:

        print(f"\n  MONDAY ITEM : '{match['name']}'")
        print(f"  LOCAL FOLDER: '{project_folder_name}'")

        confirm = input(
            "\nIs this the correct Monday project? Proceed? (Y/N): "
        ).strip().upper()

        if confirm == "Y":
            item_id = match["id"]
            break

    if item_id == "":
        raise Exception("MONDAY ITEM NOT FOUND — NO MATCH CONFIRMED")

print("\nMONDAY ITEM FOUND")

# =========================
# CONFIRM UPLOAD
# =========================

if CONFIRM_BEFORE_UPLOAD:

    confirm = input(
        "\nUPLOAD CONTRACT PDF TO MONDAY FILES? (Y/N): "
    ).strip().upper()

    if confirm != "Y":
        print("\nMONDAY UPLOAD SKIPPED")
        print("\n\nDONE\n\n")
        sys.exit()

# =========================
# UPLOAD FILE TO MONDAY
# =========================

mime_type = mimetypes.guess_type(contract_pdf)[0] or "application/pdf"

query = (
    f'mutation ($file: File!) {{'
    f'  add_file_to_column('
    f'    item_id: {item_id},'
    f'    column_id: "{files_column_id}",'
    f'    file: $file'
    f'  ) {{ id }}'
    f'}}'
)

with open(contract_pdf, "rb") as file_handle:

    response = requests.post(
        MONDAY_FILE_URL,
        headers={
            "Authorization": MONDAY_API_KEY
        },
        data={
            "query": query
        },
        files={
            "variables[file]": (
                contract_file_name,
                file_handle,
                mime_type
            )
        }
    )

print(f"\nSTATUS CODE: {response.status_code}")
print(f"RESPONSE: {response.text}")

if response.status_code != 200:
    raise Exception("MONDAY FILE UPLOAD FAILED")

upload_data = response.json()

if "errors" in upload_data:
    print(json.dumps(upload_data["errors"], indent=2))
    raise Exception("MONDAY FILE UPLOAD ERROR")

print("\nCONTRACT UPLOADED TO MONDAY FILES")
print("\n\nDONE\n\n")