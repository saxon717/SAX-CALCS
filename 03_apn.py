import os
import sys

from config import (
    find_project,
    get_project_name,
    read_info,
    update_info,
)

project_number = sys.argv[1]
force_rerun    = len(sys.argv) > 2 and sys.argv[2] == "--force"

print("UI_STEP:Reading INFO file")
sys.stdout.flush()

project_root, project_folder_name = find_project(project_number)
if not project_root:
    raise Exception("PROJECT NOT FOUND")

info_data, info_path = read_info(project_root, project_number)
if not info_path:
    raise Exception("INFO FILE NOT FOUND")

print("INFO FILE FOUND")

existing_apn = info_data.get("APN", "")
verified_apn = info_data.get("VERIFIED_APN", "")
contract_pdf = info_data.get("CONTRACT_PDF", "")

# Skip if already verified
if verified_apn and not force_rerun:
    print(f"APN already verified: {verified_apn} — skipping")
    print("DONE")
    sys.exit(0)

# Auto-confirm if APN exists but VERIFIED_APN is blank
if existing_apn and not force_rerun:
    print(f"APN found: {existing_apn} — auto-confirming")
    new_path = update_info(info_path, project_root, {"VERIFIED_APN": existing_apn})
    print(f"VERIFIED APN: {existing_apn}")
    print("DONE")
    sys.exit(0)

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

update_info(info_path, project_root, {"VERIFIED_APN": verified_apn})

print("UI_STEP:Complete")
sys.stdout.flush()
print(f"APN UPDATED: {verified_apn}")
print("DONE")