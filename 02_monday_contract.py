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

MONDAY_API_URL = "https://api.monday.com/v2"
MONDAY_FILE_URL = "https://api.monday.com/v2/file"

HEADERS = {
    "Authorization": MONDAY_API_KEY,
    "API-Version": "2023-10"
}

base_folder = (
    r"C:\Users\saxon\Dropbox\SHEAR FORCE"
    r"\1) CURRENT PROJECTS"
)

# =========================
# PROJECT NUMBER
# =========================

project_number = sys.argv[1]
year_prefix = project_number[:2]

year_folder = os.path.join(
    base_folder, f"{year_prefix}-XXX"
)

if not os.path.exists(year_folder):
    raise Exception(
        f"YEAR FOLDER NOT FOUND: {year_folder}"
    )

project_root = ""
project_folder_name = ""

for folder in os.listdir(year_folder):
    if folder.startswith(project_number):
        project_root = os.path.join(year_folder, folder)
        project_folder_name = folder
        break

if project_root == "":
    raise Exception(
        f"PROJECT FOLDER NOT FOUND FOR: {project_number}"
    )

print(f"UI_STEP:Finding contract PDF")

# =========================
# FIND CONTRACT PDF
# =========================

contract_folder = os.path.join(project_root, "CONTRACT")

if not os.path.exists(contract_folder):
    raise Exception(
        f"CONTRACT FOLDER NOT FOUND: {contract_folder}"
    )

contract_pdfs = []

for file in os.listdir(contract_folder):
    if file.lower().endswith(".pdf"):
        contract_pdfs.append(
            os.path.join(contract_folder, file)
        )

if len(contract_pdfs) == 0:
    raise Exception("NO CONTRACT PDF FOUND")

preferred_pdfs = [
    pdf for pdf in contract_pdfs
    if any(
        keyword in os.path.basename(pdf).lower()
        for keyword in [
            "proposal", "contract", "engineering services"
        ]
    )
]

if len(preferred_pdfs) > 0:
    contract_pdfs = preferred_pdfs

contract_pdf = max(
    contract_pdfs, key=os.path.getmtime
)
contract_file_name = os.path.basename(contract_pdf)

print(f"CONTRACT PDF FOUND: {contract_file_name}")

# =========================
# MONDAY API HELPER
# =========================

print(f"UI_STEP:Connecting to Monday")

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
# FIND BOARD
# =========================

print(f"UI_STEP:Finding board")

boards_data = monday_query("""
query {
  boards(limit: 100) {
    id
    name
    columns { id title type }
  }
}
""")

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
    raise Exception(
        f"MONDAY BOARD NOT FOUND: {BOARD_NAME}"
    )

print("MONDAY BOARD FOUND")

if files_column_id == "":
    raise Exception(
        f"FILES COLUMN NOT FOUND: {FILES_COLUMN}"
    )

print("FILES COLUMN FOUND")

# =========================
# FIND ITEM
# =========================

print(f"UI_STEP:Finding project item")

def fetch_all_items(board_id):
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
        next_data = monday_query("""
        query ($cursor: String!) {
          next_items_page(cursor: $cursor, limit: 500) {
            cursor
            items { id name }
          }
        }
        """, {"cursor": cursor})
        next_page = next_data["next_items_page"]
        items.extend(next_page["items"])
        cursor = next_page["cursor"]
    return items

all_items = fetch_all_items(board_id)
item_id = ""

# Exact match first
for item in all_items:
    if item["name"].strip().lower() == project_folder_name.strip().lower():
        item_id = item["id"]
        break

# Fallback — prompt UI if mismatch
if item_id == "":
    close_matches = [
        item for item in all_items
        if project_number.lower() in item["name"].strip().lower()
    ]

    if len(close_matches) == 0:
        raise Exception(
            f"MONDAY ITEM NOT FOUND — "
            f"NO CLOSE MATCHES FOR: {project_number}"
        )

    for match in close_matches:
        # Send mismatch to UI — UI will respond Y or N via stdin
        print(
            f"UI_MONDAY_MISMATCH:"
            f"{match['name']}|{project_folder_name}"
        )
        sys.stdout.flush()

        response_line = sys.stdin.readline().strip()

        if response_line == "Y":
            item_id = match["id"]
            print(
                f"USING MATCH: {match['name']}"
            )
            break

    if item_id == "":
        raise Exception(
            "MONDAY ITEM NOT FOUND — NO MATCH CONFIRMED"
        )

print("MONDAY ITEM FOUND")

# =========================
# UPLOAD FILE
# =========================

print(f"UI_STEP:Uploading file")

# =========================
# CHECK IF FILE ALREADY EXISTS IN MONDAY
# =========================

check_query = f"""
query {{
  items(ids: [{item_id}]) {{
    assets {{
      name
      url
    }}
  }}
}}
"""

check_data = monday_query(check_query)
existing_files = []

if check_data and "items" in check_data:
    for item in check_data["items"]:
        for asset in item.get("assets", []):
            existing_files.append(asset.get("name", ""))

contract_lower = contract_file_name.lower()

already_uploaded = any(
    contract_lower in f.lower() or f.lower() in contract_lower
    for f in existing_files
)

if already_uploaded:
    print(f"UI_CONTRACT_EXISTS:{contract_file_name}")
    sys.stdout.flush()
    response = sys.stdin.readline().strip()
    if response == "SKIP":
        print("CONTRACT ALREADY ON MONDAY — SKIPPING UPLOAD")
        print("DONE")
        sys.exit()
    else:
        print("RE-UPLOADING CONTRACT TO MONDAY")

mime_type = (
    mimetypes.guess_type(contract_pdf)[0]
    or "application/pdf"
)

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
        headers={"Authorization": MONDAY_API_KEY},
        data={"query": query},
        files={
            "variables[file]": (
                contract_file_name,
                file_handle,
                mime_type
            )
        }
    )

print(f"STATUS CODE: {response.status_code}")

if response.status_code != 200:
    raise Exception("MONDAY FILE UPLOAD FAILED")

upload_data = response.json()

if "errors" in upload_data:
    print(json.dumps(upload_data["errors"], indent=2))
    raise Exception("MONDAY FILE UPLOAD ERROR")

print("CONTRACT UPLOADED TO MONDAY FILES")

# Write upload status to INFO file
import glob
archive_folder = os.path.join(project_root, "CALCULATIONS", "ARCHIVE")
info_files = sorted(
    glob.glob(os.path.join(archive_folder, f"{project_number}*INFO*.txt")),
    key=os.path.getmtime, reverse=True
)
if info_files:
    with open(info_files[0], "r", encoding="utf-8") as f:
        lines = f.readlines()
    if not any(l.startswith("MONDAY_UPLOADED=") for l in lines):
        lines.append("MONDAY_UPLOADED=Y\n")
    else:
        lines = [
            f"MONDAY_UPLOADED=Y\n"
            if l.startswith("MONDAY_UPLOADED=") else l
            for l in lines
        ]
    with open(info_files[0], "w", encoding="utf-8") as f:
        f.writelines(lines)
    print("MONDAY UPLOAD STATUS SAVED TO INFO FILE")

print("DONE")