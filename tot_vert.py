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
    HEADLESS,
)

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

project_description  = ""
tot_snow_load        = ""
elevation            = ""
snow_screenshot      = ""
elevation_screenshot = ""
location_screenshot  = ""

for line in info_lines:
    if line.startswith("PROJECT_DESCRIPTION="):
        project_description = line.replace("PROJECT_DESCRIPTION=", "").strip()
    if line.startswith("TOT_SNOW_LOAD="):
        tot_snow_load = line.replace("TOT_SNOW_LOAD=", "").strip()
    if line.startswith("ELEVATION="):
        elevation = line.replace("ELEVATION=", "").strip()
    if line.startswith("TOT_SNOW_SCREENSHOT="):
        snow_screenshot = line.replace("TOT_SNOW_SCREENSHOT=", "").strip()
    if line.startswith("ELEVATION_SCREENSHOT="):
        elevation_screenshot = line.replace("ELEVATION_SCREENSHOT=", "").strip()
    if line.startswith("LOCATION_SCREENSHOT="):
        location_screenshot = line.replace("LOCATION_SCREENSHOT=", "").strip()

project_description = re.sub(r"\s+", " ", project_description).strip()
word_count          = len(project_description.split())
good_description    = word_count >= 10

# Extract numeric elevation
elevation_num = ""
if elevation:
    m = re.search(r"([\d,]+)", elevation)
    if m:
        elevation_num = m.group(1).replace(",", "")

# =========================
# FIND TOT VERT TEMPLATE
# =========================

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
# FIND TOT LAT FILE
# =========================

print("UI_STEP:Finding TOT LAT file")
sys.stdout.flush()

lat_path  = ""
lat_files = []

for file in os.listdir(calculations_folder):
    if (
        file.endswith(".xlsm")
        and "TOT LAT XL" in file.upper()
        and not file.startswith("~$")
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

print(f"TOT LAT FILE FOUND: {os.path.basename(lat_path)}")

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
# COPY TEMPLATE
# =========================

print("UI_STEP:Copying TOT VERT template")
sys.stdout.flush()

shutil.copy2(template_path, vert_path)
print(f"TOT VERT TEMPLATE COPIED: {os.path.basename(vert_path)}")

# =========================
# OPEN BOTH — hidden until done
# =========================

print("UI_STEP:Copying cover data")
sys.stdout.flush()

app = xw.App(visible=False)
app.display_alerts = False

try:
    # Close any auto-created empty books
    for book in list(app.books):
        if book.name.startswith("Book"):
            try:
                book.close()
            except:
                pass

    lat_wb  = app.books.open(os.path.abspath(lat_path))
    vert_wb = app.books.open(os.path.abspath(vert_path))

    lat_cover   = lat_wb.sheets[0]
    vert_cover  = vert_wb.sheets["COVER"]
    criteria_ws = vert_wb.sheets["Criteria"]
    cal_snow_ws = vert_wb.sheets["California Snow"]
    location_ws = vert_wb.sheets["Location"]

    # Copy cover from TOT LAT
    vert_cover.range("A10").value = lat_cover.range("A10").value
    vert_cover.range("A11").value = lat_cover.range("A11").value
    vert_cover.range("A12").value = lat_cover.range("A12").value
    vert_cover.range("A13").value = lat_cover.range("A13").value
    vert_cover.range("D35").value = lat_cover.range("D35").value
    print("TOT LAT COVER DATA COPIED")

    # Criteria sheet — elevation B15, snow load E15
    print("UI_STEP:Writing snow load")
    sys.stdout.flush()

    if elevation_num:
        criteria_ws.range("B15").value = int(elevation_num)
        print(f"ELEVATION -> Criteria B15: {elevation_num}")
    else:
        print("WARNING: No elevation value")

    if tot_snow_load:
        criteria_ws.range("E15").value = int(tot_snow_load)
        print(f"SNOW LOAD -> Criteria E15: {tot_snow_load}")
    else:
        print("WARNING: No snow load value")

    # California Snow sheet — insert screenshots stacked vertically
    print("Inserting screenshots onto California Snow sheet...")
    cal_snow_ws.activate()
    inserted = 0

    if snow_screenshot and os.path.exists(snow_screenshot):
        try:
            cal_snow_ws.pictures.add(
                os.path.abspath(snow_screenshot),
                top=cal_snow_ws.range("A3").top,
                left=cal_snow_ws.range("A3").left,
                width=400, height=200,
            )
            print("SNOW SCREENSHOT INSERTED")
            inserted += 1
        except Exception as e:
            print(f"SNOW SCREENSHOT INSERT FAILED: {e}")
    else:
        print("WARNING: Snow screenshot not found")

    if elevation_screenshot and os.path.exists(elevation_screenshot):
        try:
            cal_snow_ws.pictures.add(
                os.path.abspath(elevation_screenshot),
                top=cal_snow_ws.range("A15").top,
                left=cal_snow_ws.range("A15").left,
                width=400, height=200,
            )
            print("ELEVATION SCREENSHOT INSERTED")
            inserted += 1
        except Exception as e:
            print(f"ELEVATION SCREENSHOT INSERT FAILED: {e}")
    else:
        print("WARNING: Elevation screenshot not found")

    print(f"California Snow: {inserted}/2 screenshots inserted")

    # Location sheet — Google Maps screenshot
    print("Inserting location screenshot...")
    location_ws.activate()
    if location_screenshot and os.path.exists(location_screenshot):
        try:
            location_ws.pictures.add(
                os.path.abspath(location_screenshot),
                top=location_ws.range("A3").top,
                left=location_ws.range("A3").left,
                width=620, height=480,
            )
            print("LOCATION SCREENSHOT INSERTED")
        except Exception as e:
            print(f"LOCATION SCREENSHOT INSERT FAILED: {e}")
    else:
        print("WARNING: Location screenshot not found")

    # Snow load writeback to LAT W!B6 — TBD cell confirmation
    print("Snow load writeback to TOT LAT W!B6 — TBD")

    # Navigate to cover and save both
    vert_cover.activate()
    vert_wb.app.api.ActiveWindow.ScrollRow    = 1
    vert_wb.app.api.ActiveWindow.ScrollColumn = 1

    print("UI_STEP:Saving Excel")
    sys.stdout.flush()

    vert_wb.save()
    lat_wb.save()
    print(f"TOT VERT SAVED: {os.path.basename(vert_path)}")
    print(f"TOT LAT SAVED: {os.path.basename(lat_path)}")

    # =========================
    # REVEAL FILES + POPUP
    # If HEADLESS: keep hidden, popup asks to open
    # If not HEADLESS: make visible, popup asks to leave open
    # =========================

    print(f"UI_XL_PATH:{lat_path}")
    print(f"UI_XL_PATH:{vert_path}")
    sys.stdout.flush()

    response = sys.stdin.readline().strip()

    if response == "KEEP":
        # Make visible so user can see them
        app.visible = True
        print("XL FILES REVEALED FOR REVIEW")
    else:
        lat_wb.close()
        vert_wb.close()
        app.quit()
        print("XL FILES CLOSED")

except Exception as e:
    try: lat_wb.close()
    except: pass
    try: vert_wb.close()
    except: pass
    app.quit()
    raise e

print("TOT VERT COMPLETE")
print("DONE")