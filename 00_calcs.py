import os
import sys
import subprocess

# =========================
# OPTIONAL SETTINGS
# =========================

USE_MONDAY_UPLOAD = False


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

project_number = input(
    "\nEnter project number: "
).strip()

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
project_folder_name = ""

for folder in os.listdir(year_folder):

    if folder.startswith(project_number):

        project_root = os.path.join(
            year_folder,
            folder
        )

        project_folder_name = folder

        break

if project_root == "":

    raise Exception(
        "PROJECT NOT FOUND"
    )

# =========================
# PROJECT CONFIRM
# =========================

print("\n====================")
print("PROJECT FOUND")
print("====================")

print(f"\n{project_folder_name}")

confirm = input(
    "\nIS THIS THE CORRECT PROJECT? (Y/N): "
).strip().upper()

if confirm != "Y":

    raise Exception(
        "PROJECT NOT CONFIRMED"
    )

# =========================
# SCRIPT FOLDER
# =========================

script_folder = os.path.dirname(
    os.path.abspath(__file__)
)

# =========================
# SCRIPT PATHS
# =========================

info_script = os.path.join(
    script_folder,
    "01_info.py"
)

monday_contract_script = os.path.join(
    script_folder,
    "02_monday_contract.py"
)    

apn_script = os.path.join(
    script_folder,
    "03_apn.py"
)

tot_script = os.path.join(
    script_folder,
    "04_tot.py"
)

asce_script = os.path.join(
    script_folder,
    "05_asce.py"
)

lat_script = os.path.join(
    script_folder,
    "06_lat.py"
)

vert_script = os.path.join(
    script_folder,
    "07_vert.py"
)

sync_script = os.path.join(
    script_folder,
    "08_sync.py"
)

notify_script = os.path.join(
    script_folder,
    "09_notify.py"
)

tot_asce_script = os.path.join(
    script_folder,
    "tot_asce.py"
)

tot_lat_script = os.path.join(
    script_folder,
    "tot_lat.py"
)

tot_vert_script = os.path.join(
    script_folder,
    "tot_vert.py"
)

tot_sync_script = os.path.join(
    script_folder,
    "tot_sync.py"
)

tot_notify_script = os.path.join(
    script_folder,
    "tot_notify.py"
)

# =========================
# RUN INFO.PY
# =========================

print("\n====================")
print("RUNNING INFO.PY")
print("====================")

subprocess.run([
    sys.executable,
    info_script,
    project_number
])

# =========================
# RUN APN.PY
# =========================

print("\n====================")
print("RUNNING APN.PY")
print("====================")

subprocess.run([
    sys.executable,
    apn_script,
    project_number
])

# =========================
# RUN TOT.PY
# =========================

print("\n====================")
print("RUNNING TOT.PY")
print("====================")

subprocess.run([
    sys.executable,
    tot_script,
    project_number
])

# =========================
# ARCHIVE FOLDER
# =========================

archive_folder = os.path.join(
    project_root,
    "CALCULATIONS",
    "ARCHIVE"
)

# =========================
# FIND NEWEST INFO FILE
# =========================

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
# GET TOT STATUS
# =========================

tot_status = ""

for line in info_lines:

    if line.startswith("TOT="):

        tot_status = (
            line.replace(
                "TOT=",
                ""
            ).strip()
        )

# =========================
# NORMAL WORKFLOW
# =========================

if tot_status == "N":

    print("\n====================")
    print("NORMAL WORKFLOW")
    print("====================")

    # =========================
    # ASCE
    # =========================

    print("\nRUNNING ASCE.PY")

    subprocess.run([
        sys.executable,
        asce_script,
        project_number
    ])

    # =========================
    # LAT
    # =========================

    print("\nRUNNING LAT.PY")

    subprocess.run([
        sys.executable,
        lat_script,
        project_number
    ])

    # =========================
    # VERT
    # =========================

    print("\nRUNNING VERT.PY")

    subprocess.run([
        sys.executable,
        vert_script,
        project_number
    ])

    # =========================
    # SYNC
    # =========================

    print("\nRUNNING SYNC.PY")

    subprocess.run([
        sys.executable,
        sync_script,
        project_number
    ])

    # =========================
    # NOTIFY
    # =========================

    print("\nRUNNING NOTIFY.PY")

    subprocess.run([
        sys.executable,
        notify_script,
        project_number
    ])

# =========================
# TOT WORKFLOW
# =========================

elif tot_status == "Y":

    print("\n====================")
    print("TOT WORKFLOW")
    print("====================")

    # =========================
    # TOT ASCE
    # =========================

    print("\nRUNNING TOT_ASCE.PY")

    subprocess.run([
        sys.executable,
        tot_asce_script,
        project_number
    ])

    # =========================
    # TOT LAT
    # =========================

    print("\nRUNNING TOT_LAT.PY")

    subprocess.run([
        sys.executable,
        tot_lat_script,
        project_number
    ])

    # =========================
    # TOT VERT
    # =========================

    print("\nRUNNING TOT_VERT.PY")

    subprocess.run([
        sys.executable,
        tot_vert_script,
        project_number
    ])

    # =========================
    # TOT SYNC
    # =========================

    print("\nRUNNING TOT_SYNC.PY")

    subprocess.run([
        sys.executable,
        tot_sync_script,
        project_number
    ])

    # =========================
    # TOT NOTIFY
    # =========================

    print("\nRUNNING TOT_NOTIFY.PY")

    subprocess.run([
        sys.executable,
        tot_notify_script,
        project_number
    ])

# =========================
# INVALID TOT
# =========================

else:

    raise Exception(
        "INVALID TOT STATUS"
    )

# =========================
# COMPLETE
# =========================

print("\n====================")
print("WORKFLOW COMPLETE")
print("====================")

print("\n\nDONE\n\n")