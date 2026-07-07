import sys
import os
import shutil
import re
import xlwings as xw
from datetime import datetime

from config import (
    BASE_FOLDER,
    UI_SUBFOLDER,
    CALC_SUBFOLDER,
    YEAR_FOLDER_SUFFIX,
    TOT_TEMPLATE_FOLDER,
    TOT_VERT_TEMPLATE_NAME,
)

# =========================
# PROJECT NUMBER
# =========================

project_number = sys.argv[1]
year_prefix    = project_number[:2]
year_folder    = os.path.join(BASE_FOLDER, f"{year_prefix}{YEAR_FOLDER_SUFFIX}")

# =========================
# FIND PROJECT
# =========================

print("UI_STEP:Reading INFO file")
sys.stdout.flush()

project_root        = ""
project_folder_name = ""

for folder in os.listdir(year_folder):
    if folder.startswith(project_number):
        project_root        = os.path.join(year_folder, folder)
        project_folder_name = folder
        break

if project_root == "":
    raise Exception("PROJECT NOT FOUND")

project_name_only = (
    project_folder_name
    .replace(project_number, "")
    .strip().lstrip("-").strip()
)

# =========================
# FIND INFO FILE
# =========================

ui_folder           = os.path.join(project_root, UI_SUBFOLDER)
calculations_folder = os.path.join(project_root, CALC_SUBFOLDER)

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

with open(info_path, "r", encoding="utf-8") as f:
    info_lines = f.readlines()

project_description = ""
tot_snow_load       = ""

for line in info_lines:
    if line.startswith("PROJECT_DESCRIPTION="):
        project_description = line.replace("PROJECT_DESCRIPTION=", "").strip()
    if line.startswith("TOT_SNOW_LOAD="):
        tot_snow_load = line.replace("TOT_SNOW_LOAD=", "").strip()

project_description = re.sub(r"\s+", " ", project_description).strip()
word_count          = len(project_description.split())
good_description    = word_count >= 10

# =========================
# FIND TOT VERT TEMPLATE
# =========================

# Find TOT VERT template by partial name match
template_path = ""
for file in os.listdir(TOT_TEMPLATE_FOLDER):
    if (
        file.endswith(".xlsm")
        and TOT_VERT_TEMPLATE_NAME in file
        and "ASCE 7-16" in file
    ):
        template_path = os.path.join(TOT_TEMPLATE_FOLDER, file)
        break

if not template_path:
    raise Exception(f"TOT VERT TEMPLATE NOT FOUND IN: {TOT_TEMPLATE_FOLDER}")

print("TOT VERT TEMPLATE FOUND")

# =========================
# OUTPUT FILE NAME
# =========================

today      = datetime.now()
date_str   = f"{today.month}.{today.day}.{str(today.year)[2:]}"
vert_name  = f"{project_number} {project_name_only} - TOT VERT XL - {date_str}.xlsm"
vert_path  = os.path.join(calculations_folder, vert_name)

counter = 2
base    = os.path.splitext(vert_name)[0]
while os.path.exists(vert_path):
    vert_path = os.path.join(calculations_folder, f"{base} ({counter}).xlsm")
    counter  += 1

# =========================
# FIND TOT LAT FILE
# =========================

print("UI_STEP:Finding TOT LAT file")
sys.stdout.flush()

lat_path  = ""
lat_files = []

for file in os.listdir(calculations_folder):
    upper = file.upper()
    if (
        file.endswith(".xlsm")
        and "TOT LAT XL" in upper
    ):
        lat_files.append(file)

if not lat_files:
    raise Exception("TOT LAT WORKBOOK NOT FOUND")

latest_time = 0
for file in lat_files:
    full_path     = os.path.join(calculations_folder, file)
    modified_time = os.path.getmtime(full_path)
    if modified_time > latest_time:
        latest_time = modified_time
        lat_path    = full_path

print(f"TOT LAT FILE FOUND: {lat_path}")

# =========================
# COPY TEMPLATE
# =========================

print("UI_STEP:Copying TOT VERT template")
sys.stdout.flush()

shutil.copy2(template_path, vert_path)
print(f"TOT VERT TEMPLATE COPIED: {vert_path}")

# =========================
# OPEN BOTH FILES
# =========================

print("UI_STEP:Copying cover data")
sys.stdout.flush()

app = xw.App(visible=True)
app.display_alerts = False

try:
    lat_wb  = app.books.open(os.path.abspath(lat_path))
    vert_wb = app.books.open(os.path.abspath(vert_path))

    lat_cover  = lat_wb.sheets[0]
    vert_sheet1 = vert_wb.sheets[0]
    vert_sheet2 = vert_wb.sheets[1]
    vert_sheet3 = vert_wb.sheets[2]

    # Copy cover from TOT LAT
    vert_sheet1.range("A10").value = lat_cover.range("A10").value
    vert_sheet1.range("A11").value = lat_cover.range("A11").value
    vert_sheet1.range("A12").value = lat_cover.range("A12").value
    vert_sheet1.range("A13").value = lat_cover.range("A13").value
    vert_sheet1.range("D37").value = lat_cover.range("D35").value
    print("TOT LAT COVER DATA COPIED")

    # Update description textbox
    textbox_updated = False
    for shape in vert_sheet2.api.Shapes:
        try:
            shape_text = shape.TextFrame.Characters().Text
            if good_description and (
                "PROJECT DESCRIPTION" in shape_text.upper()
                or len(shape_text.strip()) > 20
            ):
                shape.TextFrame.Characters().Text = project_description
                textbox_updated = True
                print("TEXTBOX UPDATED")
                break
        except:
            pass

    # Snow load — update cell reference once you share sheet layout
    print("UI_STEP:Writing snow load")
    sys.stdout.flush()

    if tot_snow_load:
        # TODO: confirm cell for TOT snow load in VERT template
        print(f"TOT SNOW LOAD: {tot_snow_load} — cell TBD")
    else:
        print("WARNING: No TOT snow load — cell not updated")

    # Snow load writeback to LAT
    # TODO: confirm source cell in VERT and destination in LAT
    print("Snow load writeback to TOT LAT — cell TBD")

    vert_sheet1.activate()
    vert_wb.app.api.ActiveWindow.ScrollRow    = 1
    vert_wb.app.api.ActiveWindow.ScrollColumn = 1

    print("UI_STEP:Saving Excel")
    sys.stdout.flush()

    vert_wb.save()
    lat_wb.save()
    print(f"TOT VERT SAVED: {vert_path}")
    print(f"TOT LAT SAVED: {lat_path}")

    print(f"UI_XL_PATH:{lat_path}")
    print(f"UI_XL_PATH:{vert_path}")
    sys.stdout.flush()

    response = sys.stdin.readline().strip()
    if response == "CLOSE":
        lat_wb.close()
        vert_wb.close()
        app.quit()
        print("XL FILES CLOSED")
    else:
        print("XL FILES LEFT OPEN FOR REVIEW")

except Exception as e:
    try: lat_wb.close()
    except: pass
    try: vert_wb.close()
    except: pass
    app.quit()
    raise e

print("TOT VERT COMPLETE")
print("DONE")