import sys
import os
import shutil
import xlwings as xw
from datetime import datetime

from config import (
    find_project,
    get_project_name,
    get_ui_folder,
    get_calc_folder,
    read_info,
    update_info,
    find_template,
    make_output_path,
    TOT_TEMPLATE_FOLDER,
    TOT_LAT_TEMPLATE_NAME,
    YEAR_FOLDER_SUFFIX,
)

project_number = sys.argv[1]
project_root, project_folder_name = find_project(project_number)
if not project_root:
    raise Exception("PROJECT NOT FOUND")

project_name_only = (
    project_folder_name
    .replace(project_number, "")
    .strip().lstrip("-").strip()
)

ui_folder           = get_ui_folder(project_root)
calculations_folder = get_calc_folder(project_root)

print("UI_STEP:Reading INFO file")
sys.stdout.flush()

info_data, info_path = read_info(project_root, project_number)
if not info_path:
    raise Exception("INFO FILE NOT FOUND")

print("INFO FILE FOUND")

project_address = info_data.get("PROJECT_ADDRESS", "")
city = info_data.get("CITY", "")
state = info_data.get("STATE", "")
zip_code = info_data.get("ZIP_CODE", "")
county = info_data.get("COUNTY", "")
verified_apn = info_data.get("VERIFIED_APN", "")
ss_value = info_data.get("SEISMIC_SS", "")
s1_value = info_data.get("SEISMIC_S1", "")
fa_value = info_data.get("SEISMIC_FA", "1.2")
tl_value = info_data.get("SEISMIC_TL", "")
sms_value = info_data.get("SEISMIC_SMS", "")
sds_value = info_data.get("SEISMIC_SDS", "")
risk_category = info_data.get("SEISMIC_RISK", "II")
site_class = info_data.get("SEISMIC_CLASS", "D")

street_address       = project_address
city_state_zip       = f"{city}, {state} {zip_code}"
formatted_county_apn = f"{county} COUNTY APN: {verified_apn}" if county and verified_apn else ""
calculations_folder  = get_calc_folder(project_root)

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

# Enable macros — bypass security warning
try:
    app.api.AutomationSecurity = 1  # msoAutomationSecurityLow
except:
    pass

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
        update_info(info_path, project_root, {"ULT": ult_str})
        print(f"ULT VALUE WRITTEN TO INFO: {ult_str}")

except Exception as e:
    print(f"WARNING: Seismic Criteria sheet error: {e}")

print("UI_STEP:Inserting screenshots")
sys.stdout.flush()

cover_ws.activate()
print("UI_STEP:Saving Excel")
sys.stdout.flush()
wb.save()
print("TOT LAT COMPLETE")

# Path stored silently — VERT will emit UI_XL_PATH for both
print(f"LAT_PATH:{excel_path}")
sys.stdout.flush()

wb.close()
app.quit()

print("DONE")