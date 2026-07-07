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

project_address  = ""
city             = ""
state            = ""
zip_code         = ""
county           = ""
verified_apn     = ""
ss_value         = ""
s1_value         = ""
fa_value         = "1.2"
tl_value         = ""
sms_value        = ""
sds_value        = ""
risk_category    = "II"
site_class       = "D"

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
    if line.startswith("SEISMIC_SS="):
        ss_value = line.replace("SEISMIC_SS=", "").strip()
    if line.startswith("SEISMIC_S1="):
        s1_value = line.replace("SEISMIC_S1=", "").strip()
    if line.startswith("SEISMIC_FA="):
        v = line.replace("SEISMIC_FA=", "").strip()
        if v:
            fa_value = v
    if line.startswith("SEISMIC_TL="):
        tl_value = line.replace("SEISMIC_TL=", "").strip()
    if line.startswith("SEISMIC_SMS="):
        sms_value = line.replace("SEISMIC_SMS=", "").strip()
    if line.startswith("SEISMIC_SDS="):
        sds_value = line.replace("SEISMIC_SDS=", "").strip()
    if line.startswith("SEISMIC_RISK="):
        v = line.replace("SEISMIC_RISK=", "").strip()
        if v:
            risk_category = v
    if line.startswith("SEISMIC_CLASS="):
        v = line.replace("SEISMIC_CLASS=", "").strip()
        if v:
            site_class = v

street_address       = project_address
city_state_zip       = f"{city}, {state} {zip_code}"
formatted_county_apn = ""
if county and verified_apn:
    formatted_county_apn = f"{county} COUNTY APN: {verified_apn}"

# =========================
# FIND TOT LAT TEMPLATE
# =========================

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
print(f"TOT LAT FILE CREATED: {os.path.basename(excel_path)}")

# =========================
# OPEN AND POPULATE
# =========================

print("UI_STEP:Writing cover data")
sys.stdout.flush()

app = xw.App(visible=False)
app.display_alerts = False

# Close any auto-created empty books
for book in list(app.books):
    if book.name.startswith("Book"):
        try:
            book.close()
        except:
            pass

wb = app.books.open(os.path.abspath(excel_path))

cover_ws = wb.sheets[0]

# Cover page
cover_ws.range("D35").value = project_number
cover_ws.range("E37").value = project_number
cover_ws.range("A10").value = project_name_only
cover_ws.range("A11").value = street_address
cover_ws.range("A12").value = city_state_zip
cover_ws.range("A13").value = formatted_county_apn
print("COVER DATA WRITTEN")

# Seismic Criteria sheet
try:
    seismic_ws = wb.sheets["Seismic Criteria"]
    print("UI_STEP:Writing seismic values")
    sys.stdout.flush()

    seismic_ws.range("F4").value  = site_class
    seismic_ws.range("F6").value  = float(ss_value)  if ss_value  else None
    seismic_ws.range("F7").value  = float(fa_value)  if fa_value  else 1.2
    seismic_ws.range("F10").value = float(s1_value)  if s1_value  else None
    seismic_ws.range("F14").value = float(tl_value)  if tl_value  else None
    seismic_ws.range("F16").value = risk_category

    print(f"F4={site_class} F6={ss_value} F7={fa_value} F10={s1_value} F14={tl_value} F16={risk_category}")

    # Read D30 and write to INFO
    ult_value = seismic_ws.range("D30").value
    if ult_value is not None:
        ult_str = str(ult_value)
        print(f"D30 (ULT) = {ult_str}")
        updated = list(info_lines)
        found   = False
        for i, line in enumerate(updated):
            if line.startswith("ULT="):
                updated[i] = f"ULT={ult_str}\n"
                found = True
                break
        if not found:
            updated.append(f"ULT={ult_str}\n")
        with open(info_path, "w", encoding="utf-8") as f:
            f.writelines(updated)
        print(f"ULT VALUE WRITTEN TO INFO: {ult_str}")

except Exception as e:
    print(f"WARNING: Seismic Criteria sheet error: {e}")

cover_ws.activate()
wb.save()
print("TOT LAT COMPLETE")

# Path stored silently — VERT will emit UI_XL_PATH for both
print(f"LAT_PATH:{excel_path}")
sys.stdout.flush()

wb.close()
app.quit()

print("DONE")