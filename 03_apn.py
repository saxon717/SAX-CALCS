import os
import sys

from config import (
    BASE_FOLDER,
    UI_SUBFOLDER,
    CONTRACT_SUBFOLDER,
    YEAR_FOLDER_SUFFIX,
)
project_number = sys.argv[1]
year_prefix    = project_number[:2]
year_folder    = os.path.join(BASE_FOLDER, f"{year_prefix}{YEAR_FOLDER_SUFFIX}")

print("UI_STEP:Reading INFO file")
sys.stdout.flush()

project_root = ""
for folder in os.listdir(year_folder):
    if folder.startswith(project_number):
        project_root = os.path.join(year_folder, folder)
        break

if project_root == "":
    raise Exception("PROJECT NOT FOUND")

# =========================
# FIND INFO FILE IN UI FOLDER
# =========================

ui_folder = os.path.join(project_root, "UI")
os.makedirs(ui_folder, exist_ok=True)

info_path   = ""
latest_time = 0

for file in os.listdir(ui_folder):
    upper_file = file.upper()
    if (
        file.endswith(".txt")
        and "INFO" in upper_file
        and project_number in upper_file
    ):
        full_path     = os.path.join(ui_folder, file)
        modified_time = os.path.getmtime(full_path)
        if modified_time > latest_time:
            latest_time = modified_time
            info_path   = full_path

if info_path == "":
    raise Exception("INFO FILE NOT FOUND")

print("INFO FILE FOUND")

with open(info_path, "r", encoding="utf-8") as file:
    info_lines = file.readlines()

existing_apn = ""
contract_pdf = ""

for line in info_lines:
    if line.startswith("APN="):
        existing_apn = line.replace("APN=", "").strip()
    if line.startswith("CONTRACT_PDF="):
        contract_pdf = line.replace("CONTRACT_PDF=", "").strip()

print(f"CURRENT APN: {existing_apn}")

print("UI_STEP:Verifying APN")
sys.stdout.flush()

print(f"UI_CONFIRM_APN:{existing_apn}|{contract_pdf}")
sys.stdout.flush()

response = sys.stdin.readline().strip()

if response == "CANCELLED" or response == "":
    raise Exception("APN VERIFICATION CANCELLED")

verified_apn = response
print(f"VERIFIED APN: {verified_apn}")

print("UI_STEP:Updating INFO file")
sys.stdout.flush()

updated_lines      = []
verified_apn_found = False

for line in info_lines:
    if line.startswith("VERIFIED_APN="):
        updated_lines.append(f"VERIFIED_APN={verified_apn}\n")
        verified_apn_found = True
    else:
        updated_lines.append(line)

if not verified_apn_found:
    updated_lines.append(f"\nVERIFIED_APN={verified_apn}\n")

with open(info_path, "w", encoding="utf-8") as file:
    file.writelines(updated_lines)

print("UI_STEP:Complete")
sys.stdout.flush()
print(f"APN UPDATED: {verified_apn}")
print("DONE")