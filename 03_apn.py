import os
import sys
import time
import ctypes

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

# =========================
# YEAR PREFIX
# =========================

year_prefix = project_number[:2]

# =========================
# YEAR FOLDER
# =========================

year_folder = os.path.join(
    base_folder,
    f"{year_prefix}-XXX"
)

# =========================
# FIND PROJECT
# =========================

project_root = ""

for folder in os.listdir(year_folder):

    if folder.startswith(project_number):

        project_root = os.path.join(
            year_folder,
            folder
        )

        break

if project_root == "":

    raise Exception(
        "PROJECT NOT FOUND"
    )

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

        full_path = os.path.join(
            archive_folder,
            file
        )

        modified_time = os.path.getmtime(
            full_path
        )

        if modified_time > latest_time:

            latest_time = modified_time

            info_path = full_path

if info_path == "":

    raise Exception(
        "INFO FILE NOT FOUND"
    )

print("\nINFO FILE FOUND")
print(info_path)
# =========================
# READ INFO FILE
# =========================

with open(
    info_path,
    "r",
    encoding="utf-8"
) as file:

    info_lines = file.readlines()

# =========================
# VARIABLES
# =========================

project_address = ""
existing_apn = ""

# =========================
# EXTRACT VALUES
# =========================

for line in info_lines:

    if line.startswith("PROJECT_ADDRESS="):

        project_address = (
            line.replace(
                "PROJECT_ADDRESS=",
                ""
            ).strip()
        )

    if line.startswith("APN="):

        existing_apn = (
            line.replace(
                "APN=",
                ""
            ).strip()
        )

# =========================
# PRINT INFO
# =========================


print("\nCURRENT APN:")
print(existing_apn)


# =========================
# VERIFY APN
# =========================


apn_matches = input(
    "\nDOES THE VERIFIED APN MATCH? (Y/N): "
).strip().upper()

# =========================
# USE CURRENT APN
# =========================

if apn_matches == "Y":

    verified_apn = existing_apn

    print(
        f"\nUSING CURRENT APN:\n"
        f"{verified_apn}"
    )

# =========================
# MANUAL APN INPUT
# =========================

else:

    while True:

        verified_apn = input(
            "\nTYPE VERIFIED APN HERE: "
        ).strip()

        if len(verified_apn) != 11:

            print(
                "\nAPN MUST BE IN "
                "XXX-XXX-XXX FORMAT"
            )

            continue

        if (
            verified_apn[3] != "-"
            or verified_apn[7] != "-"
        ):

            print(
                "\nAPN MUST BE IN "
                "XXX-XXX-XXX FORMAT"
            )

            continue

        print(
            f"\nVERIFIED APN:\n"
            f"{verified_apn}"
        )

        break


# =========================
# UPDATE INFO FILE
# =========================

updated_lines = []

verified_apn_found = False

for line in info_lines:

    if line.startswith("VERIFIED_APN="):

        updated_lines.append(
            f"VERIFIED_APN="
            f"{verified_apn}\n"
        )

        verified_apn_found = True

    else:

        updated_lines.append(line)

# =========================
# ADD VERIFIED APN
# =========================

if verified_apn_found == False:

    updated_lines.append(
        f"\nVERIFIED_APN="
        f"{verified_apn}\n"
    )

# =========================
# WRITE INFO FILE
# =========================

with open(
    info_path,
    "w",
    encoding="utf-8"
) as file:

    file.writelines(updated_lines)

# =========================
# COMPLETE
# =========================

print("\n====================")
print("APN UPDATED")
print("====================")

print("\nVERIFIED APN:")
print(verified_apn)

print("\n\nDONE\n\n")