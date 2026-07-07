import sys
import os
import shutil
import xlwings as xw
from datetime import datetime

from config import (
    BASE_FOLDER,
    UI_SUBFOLDER,
    CALC_SUBFOLDER,
    YEAR_FOLDER_SUFFIX,
    TOT_TEMPLATE_FOLDER,
    TOT_LAT_TEMPLATE_NAME,
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

project_address      = ""
city                 = ""
state                = ""
zip_code             = ""
county               = ""
verified_apn         = ""
tot_snow_load        = ""
elevation            = ""
ss_value             = ""
sms_value            = ""
sds_value            = ""
s1_value             = ""
sm1_value            = ""
sd1_value            = ""
seismic_category     = ""
snow_screenshot      = ""
elevation_screenshot = ""
location_screenshot  = ""

for line in info_lines:
    if line.startswith("PROJECT_ADDRESS="):
        project_address = line.replace("PROJECT_ADDRESS=", "").strip()
    if line.startswith("CITY="):
        city = line.replace("CITY=", "").strip()
    if line.startswith("STATE="):
        state = line.replace("STATE=", "").strip()
    if line.startswith("ZIP_CODE="):
        zip_code = line.replace("ZIP_CODE=", "").strip()
    if line.startswith("COUNTY="):
        county = line.replace("COUNTY=", "").strip()
    if line.startswith("VERIFIED_APN="):
        verified_apn = line.replace("VERIFIED_APN=", "").strip()
    if line.startswith("TOT_SNOW_LOAD="):
        tot_snow_load = line.replace("TOT_SNOW_LOAD=", "").strip()
    if line.startswith("ELEVATION="):
        elevation = line.replace("ELEVATION=", "").strip()
    if line.startswith("SEISMIC_SS="):
        ss_value = line.replace("SEISMIC_SS=", "").strip()
    if line.startswith("SEISMIC_SMS="):
        sms_value = line.replace("SEISMIC_SMS=", "").strip()
    if line.startswith("SEISMIC_SDS="):
        sds_value = line.replace("SEISMIC_SDS=", "").strip()
    if line.startswith("SEISMIC_S1="):
        s1_value = line.replace("SEISMIC_S1=", "").strip()
    if line.startswith("SEISMIC_SM1="):
        sm1_value = line.replace("SEISMIC_SM1=", "").strip()
    if line.startswith("SEISMIC_SD1="):
        sd1_value = line.replace("SEISMIC_SD1=", "").strip()
    if line.startswith("SEISMIC_CATEGORY="):
        seismic_category = line.replace("SEISMIC_CATEGORY=", "").strip()
    if line.startswith("TOT_SNOW_SCREENSHOT="):
        snow_screenshot = line.replace("TOT_SNOW_SCREENSHOT=", "").strip()
    if line.startswith("ELEVATION_SCREENSHOT="):
        elevation_screenshot = line.replace("ELEVATION_SCREENSHOT=", "").strip()
    if line.startswith("LOCATION_SCREENSHOT="):
        location_screenshot = line.replace("LOCATION_SCREENSHOT=", "").strip()

street_address       = project_address
city_state_zip       = f"{city}, {state} {zip_code}"
formatted_county_apn = ""
if county and verified_apn:
    formatted_county_apn = f"{county} COUNTY APN: {verified_apn}"

# Extract numeric elevation for cell write
elevation_num = ""
if elevation:
    import re
    m = re.search(r"([\d,]+)", elevation)
    if m:
        elevation_num = m.group(1).replace(",", "")

# =========================
# FIND TOT LAT TEMPLATE
# =========================

# Find TOT LAT template by partial name match
template_path = ""
for file in os.listdir(TOT_TEMPLATE_FOLDER):
    if (
        file.endswith(".xlsm")
        and TOT_LAT_TEMPLATE_NAME in file
        and "ASCE 7-16" in file
    ):
        template_path = os.path.join(TOT_TEMPLATE_FOLDER, file)
        break

if not template_path:
    raise Exception(f"TOT LAT TEMPLATE NOT FOUND IN: {TOT_TEMPLATE_FOLDER}")

print("TOT LAT TEMPLATE FOUND")

# =========================
# OUTPUT FILE NAME
# =========================

today      = datetime.now()
date_str   = f"{today.month}.{today.day}.{str(today.year)[2:]}"
excel_name = f"{project_number} {project_name_only} - TOT LAT XL - {date_str}.xlsm"
excel_path = os.path.join(calculations_folder, excel_name)

counter = 2
base    = os.path.splitext(excel_name)[0]
while os.path.exists(excel_path):
    excel_path = os.path.join(calculations_folder, f"{base} ({counter}).xlsm")
    counter   += 1

# =========================
# COPY TEMPLATE
# =========================

print("UI_STEP:Copying TOT LAT template")
sys.stdout.flush()

shutil.copy(template_path, excel_path)
print(f"TOT LAT FILE CREATED: {excel_path}")

# =========================
# OPEN AND POPULATE
# =========================

print("UI_STEP:Writing cover data")
sys.stdout.flush()

app = xw.App(visible=True)
app.display_alerts = False

wb = app.books.open(os.path.abspath(excel_path))

# Get sheet references
try:
    cover_ws    = wb.sheets[0]
    criteria_ws = wb.sheets["Criteria"]
    cal_snow_ws = wb.sheets["California Snow"]
    location_ws = wb.sheets["Location"]
except Exception as e:
    print(f"WARNING: Sheet access error: {e}")
    cover_ws    = wb.sheets[0]
    criteria_ws = None
    cal_snow_ws = None
    location_ws = None

# Cover page
cover_ws.range("D35").value = project_number
cover_ws.range("A10").value = project_name_only
cover_ws.range("A11").value = street_address
cover_ws.range("A12").value = city_state_zip
cover_ws.range("A13").value = formatted_county_apn
print("COVER DATA WRITTEN")

# Criteria sheet — elevation B15, snow load E15
if criteria_ws:
    print("UI_STEP:Writing seismic values")
    sys.stdout.flush()
    if elevation_num:
        criteria_ws.range("B15").value = int(elevation_num)
        print(f"ELEVATION → Criteria B15: {elevation_num}")
    else:
        print("WARNING: No elevation value for Criteria B15")

    if tot_snow_load:
        criteria_ws.range("E15").value = int(tot_snow_load)
        print(f"SNOW LOAD → Criteria E15: {tot_snow_load}")
    else:
        print("WARNING: No snow load value for Criteria E15")

    if ss_value:
        criteria_ws.range("F4").value  = seismic_category
        criteria_ws.range("F6").value  = ss_value
        criteria_ws.range("F7").value  = sms_value
        criteria_ws.range("F8").value  = sds_value
        criteria_ws.range("F9").value  = s1_value
        criteria_ws.range("F10").value = sm1_value
        criteria_ws.range("F11").value = sd1_value
        print("SEISMIC VALUES WRITTEN TO CRITERIA")
    else:
        print("WARNING: No seismic values in INFO — cells not updated")

# California Snow sheet — insert screenshots stacked vertically
if cal_snow_ws:
    print("Inserting screenshots onto California Snow sheet...")
    cal_snow_ws.activate()
    inserted_count = 0

    # Top screenshot — TOT snow popup
    if snow_screenshot and os.path.exists(snow_screenshot):
        try:
            cal_snow_ws.pictures.add(
                os.path.abspath(snow_screenshot),
                top=cal_snow_ws.range("A3").top,
                left=cal_snow_ws.range("A3").left,
                width=400,
                height=200,
            )
            print("SNOW LOAD SCREENSHOT INSERTED")
            inserted_count += 1
        except Exception as e:
            print(f"SNOW SCREENSHOT INSERT FAILED: {e}")
    else:
        print("WARNING: TOT snow screenshot not found — insert manually")

    # Bottom screenshot — elevation
    if elevation_screenshot and os.path.exists(elevation_screenshot):
        try:
            cal_snow_ws.pictures.add(
                os.path.abspath(elevation_screenshot),
                top=cal_snow_ws.range("A15").top,
                left=cal_snow_ws.range("A15").left,
                width=400,
                height=200,
            )
            print("ELEVATION SCREENSHOT INSERTED")
            inserted_count += 1
        except Exception as e:
            print(f"ELEVATION SCREENSHOT INSERT FAILED: {e}")
    else:
        print("WARNING: Elevation screenshot not found — insert manually")

    print(f"California Snow: {inserted_count}/2 screenshots inserted")

# Location sheet — insert Google Maps satellite screenshot
if location_ws:
    print("Inserting location screenshot onto Location sheet...")
    location_ws.activate()
    if location_screenshot and os.path.exists(location_screenshot):
        try:
            location_ws.pictures.add(
                os.path.abspath(location_screenshot),
                top=location_ws.range("A3").top,
                left=location_ws.range("A3").left,
                width=620,
                height=480,
            )
            print("LOCATION SCREENSHOT INSERTED")
        except Exception as e:
            print(f"LOCATION SCREENSHOT INSERT FAILED: {e}")
    else:
        print("WARNING: Location screenshot not found — insert manually")

cover_ws.activate()
wb.app.api.ActiveWindow.ScrollRow    = 1
wb.app.api.ActiveWindow.ScrollColumn = 1

wb.save()
print("TOT LAT COMPLETE")

print(f"UI_XL_PATH:{excel_path}")
sys.stdout.flush()

print("DONE")