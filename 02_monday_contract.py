import os
import sys
import json
import glob
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

project_number = sys.argv[1]
year_prefix    = project_number[:2]

year_folder = os.path.join(base_folder, f"{year_prefix}-XXX")

if not os.path.exists(year_folder):
    raise Exception(f"YEAR FOLDER NOT FOUND: {year_folder}")

project_root        = ""
project_folder_name = ""

for folder in os.listdir(year_folder):
    if folder.startswith(project_number):
        project_root        = os.path.join(year_folder, folder)
        project_folder_name = folder
        break

if not project_root:
    raise Exception(f"PROJECT FOLDER NOT FOUND: {project_number}")

# =========================
# FIND LATEST INFO FILE
# =========================

archive_folder = os.path.join(
    project_root, "CALCULATIONS", "ARCHIVE"
)

info_files = sorted(
    [
        os.path.join(archive_folder, f)
        for f in os.listdir(archive_folder)
        if f.endswith(".txt")
        and "INFO" in f.upper()
        and project_number in f.upper()
    ],
    key=os.path.getmtime,
    reverse=True
)

info_path = info_files[0] if info_files else ""

def read_info():
    if not info_path:
        return {}
    data = {}
    with open(info_path, "r", encoding="utf-8") as f:
        for line in f:
            if "=" in line:
                k, _, v = line.partition("=")
                data[k.strip()] = v.strip()
    return data

def write_monday_uploaded(value):
    if not info_path:
        return
    with open(info_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    updated = []
    found = False
    for line in lines:
        if line.startswith("MONDAY_UPLOADED="):
            updated.append(f"MONDAY_UPLOADED={value}\n")
            found = True
        else:
            updated.append(line)
    if not found:
        updated.append(f"MONDAY_UPLOADED={value}\n")
    with open(info_path, "w", encoding="utf-8") as f:
        f.writelines(updated)

# =========================
# CHECK INFO FILE FIRST
# =========================

info_data = read_info()
monday_uploaded = info_data.get("MONDAY_UPLOADED", "").strip()

if monday_uploaded == "Y":
    print("MONDAY_UPLOADED=Y IN INFO FILE — SKIPPING")
    print("DONE")
    sys.exit()

# =========================
# FIND CONTRACT PDF
# =========================

print("UI_STEP:Finding contract PDF")
sys.stdout.flush()

contract_folder = os.path.join(project_root, "CONTRACT")

if not os.path.exists(contract_folder):
    raise Exception(f"CONTRACT FOLDER NOT FOUND: {contract_folder}")

contract_pdfs = []
for file in os.listdir(contract_folder):
    if file.lower().endswith(".pdf"):
        contract_pdfs.append(os.path.join(contract_folder, file))

if not contract_pdfs:
    raise Exception("NO CONTRACT PDF FOUND")

preferred = [
    pdf for pdf in contract_pdfs
    if any(
        kw in os.path.basename(pdf).lower()
        for kw in ["proposal", "contract", "engineering services"]
    )
]

if preferred:
    contract_pdfs = preferred

contract_pdf       = max(contract_pdfs, key=os.path.getmtime)
contract_file_name = os.path.basename(contract_pdf)

print(f"CONTRACT PDF FOUND: {contract_file_name}")
sys.stdout.flush()

# =========================
# CONNECT TO MONDAY
# =========================

print("UI_STEP:Connecting to Monday")
sys.stdout.flush()

def monday_query(query, variables=None):
    response = requests.post(
        MONDAY_API_URL,
        headers=HEADERS,
        json={"query": query, "variables": variables or {}}
    )
    if response.status_code != 200:
        raise Exception(f"MONDAY API FAILED: {response.status_code}")
    data = response.json()
    if "errors" in data:
        raise Exception(f"MONDAY GRAPHQL ERROR: {data['errors']}")
    return data["data"]

# =========================
# FIND BOARD
# =========================

print("UI_STEP:Finding board")
sys.stdout.flush()

boards_data = monday_query("""
query {
  boards(limit: 100) {
    id name
    columns { id title type }
  }
}
""")

board_id       = ""
files_column_id = ""

for board in boards_data["boards"]:
    if board["name"].strip().lower() == BOARD_NAME.strip().lower():
        board_id = board["id"]
        for col in board["columns"]:
            if col["title"].strip().lower() == FILES_COLUMN.strip().lower():
                files_column_id = col["id"]
        break

if not board_id:
    raise Exception(f"MONDAY BOARD NOT FOUND: {BOARD_NAME}")
if not files_column_id:
    raise Exception(f"FILES COLUMN NOT FOUND: {FILES_COLUMN}")

print("MONDAY BOARD FOUND")

# =========================
# FIND ITEM
# =========================

print("UI_STEP:Finding project item")
sys.stdout.flush()

def fetch_all_items(board_id):
    items = []
    data  = monday_query("""
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
item_id   = ""

for item in all_items:
    if item["name"].strip().lower() == project_folder_name.strip().lower():
        item_id = item["id"]
        break

if not item_id:
    close_matches = [
        item for item in all_items
        if project_number.lower() in item["name"].strip().lower()
    ]
    if not close_matches:
        raise Exception(f"MONDAY ITEM NOT FOUND: {project_number}")
    for match in close_matches:
        print(f"UI_MONDAY_MISMATCH:{match['name']}|{project_folder_name}")
        sys.stdout.flush()
        response = sys.stdin.readline().strip()
        if response == "Y":
            item_id = match["id"]
            break
    if not item_id:
        raise Exception("MONDAY ITEM NOT FOUND — NO MATCH CONFIRMED")

print("MONDAY ITEM FOUND")

# =========================
# CHECK IF FILE ALREADY ON MONDAY
# (silent — no popup)
# =========================

print("Checking Monday for existing contract...")
sys.stdout.flush()

check_data = monday_query(f"""
query {{
  items(ids: [{item_id}]) {{
    assets {{
      name
    }}
  }}
}}
""")

existing_files = []
if check_data and "items" in check_data:
    for item in check_data["items"]:
        for asset in item.get("assets", []):
            existing_files.append(asset.get("name", "").lower())

contract_lower = contract_file_name.lower()

already_on_monday = any(
    contract_lower in f or f in contract_lower
    for f in existing_files
)

if already_on_monday:
    print("CONTRACT ALREADY ON MONDAY — SKIPPING UPLOAD")
    write_monday_uploaded("Y")
    print("INFO FILE UPDATED: MONDAY_UPLOADED=Y")
    print("DONE")
    sys.exit()

# =========================
# FILE NOT ON MONDAY — ASK TO UPLOAD
# =========================

print("UI_STEP:Uploading file")
sys.stdout.flush()

print(f"UI_UPLOAD_CONFIRM:{contract_file_name}")
sys.stdout.flush()

response = sys.stdin.readline().strip()

if response == "SKIP":
    print("MONDAY UPLOAD SKIPPED")
    print("DONE")
    sys.exit()

# =========================
# UPLOAD
# =========================

print("Uploading contract to Monday...")
sys.stdout.flush()

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
        headers={"Authorization": MONDAY_API_KEY},
        data={"query": query},
        files={"variables[file]": (contract_file_name, file_handle, mime_type)}
    )

print(f"STATUS CODE: {response.status_code}")

if response.status_code != 200:
    raise Exception("MONDAY FILE UPLOAD FAILED")

upload_data = response.json()
if "errors" in upload_data:
    raise Exception(f"MONDAY FILE UPLOAD ERROR: {upload_data['errors']}")

print("CONTRACT UPLOADED TO MONDAY FILES")

# Update INFO file
write_monday_uploaded("Y")
print("INFO FILE UPDATED: MONDAY_UPLOADED=Y")
print("DONE")