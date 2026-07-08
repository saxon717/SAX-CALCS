import sys
import os
import shutil
import re
from datetime import datetime

import pdfplumber
import xlwings as xw

from config import (
    find_project,
    get_project_name,
    get_ui_folder,
    get_calc_folder,
    read_info,
    find_template,
    find_xl_file,
    make_output_path,
    TEMPLATE_FOLDER,
    VERT_TEMPLATE_NAME,
    YEAR_FOLDER_SUFFIX,
    HEADLESS,
)


# =========================
# PROJECT NUMBER
# =========================

project_number = sys.argv[1]
project_root, project_folder_name = find_project(project_number)
if not project_root:
    raise Exception("PROJECT NOT FOUND")

project_name_only = (
    project_folder_name
    .replace(project_number, "")
    .strip()
    .lstrip("-")
    .strip()
)

# =========================
# FOLDERS
# =========================

calculations_folder = os.path.join(
    project_root, "CALCULATIONS"
)
ui_folder = get_ui_folder(project_root)
# =========================
# FIND NEWEST INFO FILE
# =========================

info_data, info_path = read_info(project_root, project_number)
if not info_path:
    raise Exception("INFO FILE NOT FOUND")

print("INFO FILE FOUND")

# =========================
# READ INFO FILE
# =========================

project_description = info_data.get("PROJECT_DESCRIPTION", "")


# =========================
# FIND VERT TEMPLATE
# =========================

template_folder = TEMPLATE_FOLDER

template_path = ""

for file in os.listdir(template_folder):
    if (
        file.endswith(".xlsm")
        and VERT_TEMPLATE_NAME in file
    ):
        template_path = os.path.join(
            template_folder, file
        )
        break

if template_path == "":
    raise Exception("VERT TEMPLATE NOT FOUND")

print(f"VERT TEMPLATE FOUND: {template_path}")

# =========================
# DATE STRING
# =========================

today = datetime.now()
formatted_date = (
    f"{today.month}."
    f"{today.day}."
    f"{str(today.year)[2:]}"
)

# =========================
# NEW VERT FILE NAME
# =========================

base_vert_filename = (
    f"{project_number} {project_name_only}"
    f" - VERT XL - {formatted_date}"
)

vert_filename = f"{base_vert_filename}.xlsm"
vert_path = os.path.join(
    calculations_folder, vert_filename
)

counter = 2
while os.path.exists(vert_path):
    vert_filename = f"{base_vert_filename} ({counter}).xlsm"
    vert_path = os.path.join(
        calculations_folder, vert_filename
    )
    counter += 1

# =========================
# COPY TEMPLATE
# =========================

print("UI_STEP:Copying template")
sys.stdout.flush()

shutil.copy2(template_path, vert_path)
print(f"VERT TEMPLATE COPIED: {vert_path}")

# =========================
# FIND LAT FILE
# =========================

print("UI_STEP:Finding LAT file")
sys.stdout.flush()

lat_path  = ""
lat_files = []

for file in os.listdir(calculations_folder):
    upper_file = file.upper()
    if (
        file.endswith(".xlsm")
        and "LAT XL" in upper_file
        and "VERT" not in upper_file
        and not file.startswith("~$")
    ):
        lat_files.append(file)

if len(lat_files) == 0:
    raise Exception("LAT WORKBOOK NOT FOUND")

latest_time = 0
for file in lat_files:
    full_path = os.path.join(calculations_folder, file)
    modified_time = os.path.getmtime(full_path)
    if modified_time > latest_time:
        latest_time = modified_time
        lat_path = full_path

print(f"LAT FILE FOUND: {lat_path}")

# =========================
# FIND ASCE PDF
# =========================

asce_pdf  = ""
pdf_files = []

for file in os.listdir(calculations_folder):
    if (
        file.endswith(".pdf")
        and "ASCEDesignHazardsReport" in file
    ):
        pdf_files.append(file)

if len(pdf_files) == 0:
    raise Exception("ASCE PDF NOT FOUND")

latest_time = 0
for file in pdf_files:
    full_path = os.path.join(calculations_folder, file)
    modified_time = os.path.getmtime(full_path)
    if modified_time > latest_time:
        latest_time = modified_time
        asce_pdf = full_path

print(f"ASCE PDF FOUND: {asce_pdf}")

# =========================
# CLEAN DESCRIPTION
# =========================

project_description = re.sub(
    r"\s+", " ", project_description
).strip()

word_count = len(project_description.split())
good_description = word_count >= 10

if good_description:
    print(f"GOOD DESCRIPTION — {word_count} words")
else:
    print("BAD DESCRIPTION — skipping textbox update")

# =========================
# EXTRACT SNOW LOAD
# =========================

print("UI_STEP:Copying cover data")
sys.stdout.flush()

snow_load = ""

with pdfplumber.open(asce_pdf) as pdf:
    page_5    = pdf.pages[4]
    page_text = page_5.extract_text()

snow_match = re.search(
    r"Ground snow load.*?(\d+)\s*lb",
    page_text,
    re.IGNORECASE | re.DOTALL
)

if snow_match:
    snow_load = snow_match.group(1)

print(f"SNOW LOAD: {snow_load}")

# =========================
# OPEN BOTH FILES SIDE BY SIDE
# LAT stays open — snow load written back after VERT done
# =========================

app = xw.App(visible=True)
app.display_alerts = False

try:
    lat_wb  = app.books.open(os.path.abspath(lat_path))
    vert_wb = app.books.open(os.path.abspath(vert_path))

    lat_cover_ws = lat_wb.sheets[0]
    vert_sheet_1 = vert_wb.sheets[0]
    vert_sheet_2 = vert_wb.sheets[1]
    vert_sheet_3 = vert_wb.sheets[2]

    # =========================
    # COPY COVER FROM LAT TO VERT
    # =========================

    vert_sheet_1.range("A10").value = lat_cover_ws.range("A10").value
    vert_sheet_1.range("A11").value = lat_cover_ws.range("A11").value
    vert_sheet_1.range("A12").value = lat_cover_ws.range("A12").value
    vert_sheet_1.range("A13").value = lat_cover_ws.range("A13").value
    vert_sheet_1.range("D37").value = lat_cover_ws.range("D35").value

    print("LAT COVER DATA COPIED")

    # =========================
    # UPDATE TEXTBOX
    # =========================

    textbox_updated = False

    for shape in vert_sheet_2.api.Shapes:
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

    if good_description and not textbox_updated:
        raise Exception("TEXTBOX NOT FOUND")

    # =========================
    # WRITE SNOW LOAD TO VERT
    # =========================

    print("UI_STEP:Writing snow load")
    sys.stdout.flush()

    if snow_load != "":
        vert_sheet_3.range("F17").value = snow_load
        print("SNOW LOAD WRITTEN TO VERT")

    # =========================
    # READ ROOF SNOW LOAD FROM VERT Criteria!D48
    # WRITE BACK TO LAT W!B6
    # =========================

    print("Writing roof snow load back to LAT...")
    sys.stdout.flush()

    try:
        criteria_ws      = vert_wb.sheets["Criteria"]
        roof_snow_load   = criteria_ws.range("D48").value
        lat_w_ws         = lat_wb.sheets["W"]
        lat_w_ws.range("B6").value = roof_snow_load
        print(f"ROOF SNOW LOAD → LAT W!B6: {roof_snow_load}")
    except Exception as e:
        print(f"WARNING: Could not write snow load to LAT: {e}")

    # =========================
    # NAVIGATE + SAVE BOTH
    # =========================

    vert_sheet_1.activate()
    vert_wb.app.api.ActiveWindow.ScrollRow    = 1
    vert_wb.app.api.ActiveWindow.ScrollColumn = 1

    print("UI_STEP:Saving Excel")
    sys.stdout.flush()

    vert_wb.save()
    lat_wb.save()
    print(f"VERT SAVED: {vert_path}")
    print(f"LAT SAVED: {lat_path}")

    # =========================
    # WAIT FOR UI RESPONSE — keep open or close
    # =========================

    print(f"UI_XL_PATH:{lat_path}")
    print(f"UI_XL_PATH:{vert_path}")
    sys.stdout.flush()

    # Runner will emit req_xl_complete and wait for result
    response = sys.stdin.readline().strip()

    if response == "CLOSE":
        lat_wb.close()
        vert_wb.close()
        app.quit()
        print("XL FILES CLOSED")
    else:
        # KEEP — leave open, just detach xlwings
        print("XL FILES LEFT OPEN FOR REVIEW")

except Exception as e:
    try:
        lat_wb.close()
    except:
        pass
    try:
        vert_wb.close()
    except:
        pass
    app.quit()
    raise e

print("VERT COMPLETE")
print("DONE")