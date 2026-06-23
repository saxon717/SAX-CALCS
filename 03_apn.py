import os
import sys

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

year_folder = os.path.join(
    base_folder,
    f"{year_prefix}-XXX"
)

# =========================
# FIND PROJECT
# =========================

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
# FIND NEWEST INFO FILE
# =========================

archive_folder = os.path.join(
    project_root,
    "CALCULATIONS",
    "ARCHIVE"
)

info_path = ""
latest_time = 0

for file in os.listdir(archive_folder):
    upper_file = file.upper()
    if (
        file.endswith(".txt")
        and "INFO" in upper_file
        and project_number in upper_file
    ):
        full_path = os.path.join(archive_folder, file)
        modified_time = os.path.getmtime(full_path)
        if modified_time > latest_time:
            latest_time = modified_time
            info_path = full_path

if info_path == "":
    raise Exception("INFO FILE NOT FOUND")

print("INFO FILE FOUND")

# =========================
# READ INFO FILE
# =========================

with open(info_path, "r", encoding="utf-8") as file:
    info_lines = file.readlines()

# =========================
# EXTRACT VALUES
# =========================

existing_apn = ""

for line in info_lines:
    if line.startswith("APN="):
        existing_apn = line.replace("APN=", "").strip()

print(f"CURRENT APN: {existing_apn}")

# =========================
# SEND APN TO UI FOR VERIFICATION
# =========================

print("UI_STEP:Verifying APN")
sys.stdout.flush()

# UI will show the APN dialog and return either
# the confirmed/corrected APN or CANCELLED
print(f"UI_CONFIRM_APN:{existing_apn}")
sys.stdout.flush()

response = sys.stdin.readline().strip()

if response == "CANCELLED" or response == "":
    raise Exception("APN VERIFICATION CANCELLED")

verified_apn = response

print(f"VERIFIED APN: {verified_apn}")

# =========================
# UPDATE INFO FILE
# =========================

print("UI_STEP:Updating INFO file")
sys.stdout.flush()

updated_lines = []
verified_apn_found = False

for line in info_lines:
    if line.startswith("VERIFIED_APN="):
        updated_lines.append(
            f"VERIFIED_APN={verified_apn}\n"
        )
        verified_apn_found = True
    else:
        updated_lines.append(line)

if not verified_apn_found:
    updated_lines.append(
        f"\nVERIFIED_APN={verified_apn}\n"
    )

with open(info_path, "w", encoding="utf-8") as file:
    file.writelines(updated_lines)

# =========================
# COMPLETE
# =========================

print("UI_STEP:Complete")
sys.stdout.flush()

print(f"APN UPDATED: {verified_apn}")
print("DONE")