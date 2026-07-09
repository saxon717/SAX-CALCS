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
    cleanup_xl_locks,
)

project_number = sys.argv[1]

print("UI_STEP:Reading INFO file")
sys.stdout.flush()

project_root, project_folder_name = find_project(project_number)
if not project_root:
    raise Exception("PROJECT NOT FOUND")

project_name_only   = get_project_name(project_folder_name, project_number)
calculations_folder = get_calc_folder(project_root)

info_data, info_path = read_info(project_root, project_number)
if not info_path:
    raise Exception("INFO FILE NOT FOUND")

print("INFO FILE FOUND")

project_address  = info_data.get("PROJECT_ADDRESS", "")
city             = info_data.get("CITY", "")
state            = info_data.get("STATE", "")
zip_code         = info_data.get("ZIP_CODE", "")
county           = info_data.get("COUNTY", "")
verified_apn     = info_data.get("VERIFIED_APN", "")
ss_value         = info_data.get("SEISMIC_SS", "")
s1_value         = info_data.get("SEISMIC_S1", "")
fa_value         = info_data.get("SEISMIC_FA", "1.2")
tl_value         = info_data.get("SEISMIC_TL", "")
sms_value        = info_data.get("SEISMIC_SMS", "")
sds_value        = info_data.get("SEISMIC_SDS", "")
risk_category    = info_data.get("SEISMIC_RISK", "II")
site_class       = info_data.get("SEISMIC_CLASS", "D")
tot_snow_load    = info_data.get("TOT_SNOW_LOAD", "")

street_address       = project_address
city_state_zip       = f"{city}, {state} {zip_code}"
formatted_county_apn = f"{county} COUNTY APN: {verified_apn}" if county and verified_apn else ""

# =========================
# FIND EXISTING LAT FILES
# =========================

existing_lat_files = []
for file in os.listdir(calculations_folder):
    if (
        file.endswith(".xlsm")
        and "TOT LAT XL" in file.upper()
        and not file.startswith("~$")
    ):
        existing_lat_files.append(
            os.path.join(calculations_folder, file)
        )

existing_lat_files.sort(key=os.path.getmtime, reverse=True)

# =========================
# ASK USER — UPDATE OR CREATE NEW
# =========================

excel_path = ""
mode       = "NEW"

if existing_lat_files:
    files_str = "|".join(["TOT LAT XL"] + existing_lat_files)
    print(f"UI_XL_SELECT:{files_str}")
    sys.stdout.flush()
    response = sys.stdin.readline().strip()
    if response.startswith("UPDATE:"):
        excel_path = response.replace("UPDATE:", "").strip()
        mode       = "UPDATE"
        print(f"UPDATING EXISTING: {os.path.basename(excel_path)}")
    else:
        mode = "NEW"
        print("CREATING NEW FROM TEMPLATE")

if mode == "NEW":
    # Find template
    template_path = find_template(
        TOT_TEMPLATE_FOLDER, TOT_LAT_TEMPLATE_NAME,
        extension=".xlsm", extra_match="ASCE 7-16"
    )
    if not template_path:
        raise Exception(f"TOT LAT TEMPLATE NOT FOUND IN: {TOT_TEMPLATE_FOLDER}")
    print("TOT LAT TEMPLATE FOUND")

    print("UI_STEP:Copying TOT LAT template")
    sys.stdout.flush()
    excel_path = make_output_path(
        calculations_folder, project_number,
        project_name_only, "TOT LAT XL"
    )
    shutil.copy(template_path, excel_path)
    print(f"TOT LAT FILE CREATED: {os.path.basename(excel_path)}")

# =========================
# OPEN AND POPULATE
# =========================

print("UI_STEP:Writing cover data")
sys.stdout.flush()

# Clean up stale lock files before opening
cleanup_xl_locks(calculations_folder)

app = xw.App(visible=False)
app.display_alerts = False
try:
    app.api.AutomationSecurity = 1
except:
    pass

for book in list(app.books):
    if book.name.startswith("Book"):
        try: book.close()
        except: pass

wb       = app.books.open(os.path.abspath(excel_path))
cover_ws = wb.sheets[0]

def cell_differs(ws, cell, value):
    """Return True if cell value differs from given value."""
    try:
        current = ws.range(cell).value
        if current is None and not value:
            return False
        return str(current).strip() != str(value).strip()
    except:
        return True

# Cover page — only update if different
if cell_differs(cover_ws, "D35", project_number):
    cover_ws.range("D35").value = project_number
if cell_differs(cover_ws, "E37", project_number):
    cover_ws.range("E37").value = project_number
if cell_differs(cover_ws, "A10", project_name_only):
    cover_ws.range("A10").value = project_name_only
if cell_differs(cover_ws, "A11", street_address):
    cover_ws.range("A11").value = street_address
if cell_differs(cover_ws, "A12", city_state_zip):
    cover_ws.range("A12").value = city_state_zip
if cell_differs(cover_ws, "A13", formatted_county_apn):
    cover_ws.range("A13").value = formatted_county_apn
print("COVER DATA WRITTEN")

# Seismic Criteria sheet
try:
    seismic_ws = wb.sheets["Seismic Criteria"]
    print("UI_STEP:Writing seismic values")
    sys.stdout.flush()

    def write_if_different(ws, cell, value):
        if value and cell_differs(ws, cell, value):
            try:
                ws.range(cell).value = float(value)
            except:
                ws.range(cell).value = value

    write_if_different(seismic_ws, "F6",  ss_value)
    write_if_different(seismic_ws, "F7",  fa_value or "1.2")
    write_if_different(seismic_ws, "F10", s1_value)
    write_if_different(seismic_ws, "F14", tl_value)

    if cell_differs(seismic_ws, "F4",  site_class):
        seismic_ws.range("F4").value = site_class
    if cell_differs(seismic_ws, "F16", risk_category):
        seismic_ws.range("F16").value = risk_category

    print(f"F4={site_class} F6={ss_value} F7={fa_value} F10={s1_value} F14={tl_value} F16={risk_category}")

    # Write snow load to Seismic Criteria!I2
    if tot_snow_load:
        try:
            seismic_ws.range("I2").value = int(tot_snow_load)
            print(f"SNOW LOAD -> Seismic Criteria!I2: {tot_snow_load}")
        except Exception as e:
            print(f"WARNING: Seismic Criteria I2 write failed: {e}")

    # Read D30 ULT value
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

print("UI_STEP:Saving Excel")
sys.stdout.flush()

cover_ws.activate()
wb.save()
print("TOT LAT COMPLETE")

print(f"LAT_PATH:{excel_path}")
sys.stdout.flush()

wb.close()
app.quit()

print("DONE")