import sys
import os
import shutil
import re
import xlwings as xw
from datetime import datetime

from config import (
    find_project,
    get_project_name,
    get_ui_folder,
    get_calc_folder,
    read_info,
    find_template,
    find_xl_file,
    make_output_path,
    TOT_TEMPLATE_FOLDER,
    TOT_VERT_TEMPLATE_NAME,
    HEADLESS,
    YEAR_FOLDER_SUFFIX,
    cleanup_xl_locks,
)

project_number = sys.argv[1]

def cell_differs(ws, cell, value):
    """Return True if cell value differs from given value."""
    try:
        current = ws.range(cell).value
        if current is None and not value:
            return False
        return str(current).strip() != str(value).strip()
    except:
        return True

def sheet_has_picture(ws):
    """Return True if sheet already has at least one picture."""
    try:
        return len(ws.pictures) > 0
    except:
        return False

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

project_description = info_data.get("PROJECT_DESCRIPTION", "")
tot_snow_load = info_data.get("TOT_SNOW_LOAD", "")
elevation = info_data.get("ELEVATION", "")
snow_screenshot = info_data.get("TOT_SNOW_SCREENSHOT", "")
location_screenshot = info_data.get("LOCATION_SCREENSHOT", "")

import re as _re
project_description = _re.sub(r"\s+", " ", project_description).strip()
word_count          = len(project_description.split())
good_description    = word_count >= 10

# Extract numeric elevation
elevation_num = ""
if elevation:
    m = _re.search(r"([\d,]+)", elevation)
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
# FIND EXISTING VERT FILES
# =========================

existing_vert_files = []
for file in os.listdir(calculations_folder):
    if (
        file.endswith(".xlsm")
        and "TOT VERT XL" in file.upper()
        and not file.startswith("~$")
    ):
        existing_vert_files.append(os.path.join(calculations_folder, file))
existing_vert_files.sort(key=os.path.getmtime, reverse=True)

vert_path = ""
vert_mode = "NEW"

if existing_vert_files:
    files_str = "|".join(["TOT VERT XL"] + existing_vert_files)
    print(f"UI_XL_SELECT:{files_str}")
    sys.stdout.flush()
    response = sys.stdin.readline().strip()
    if response.startswith("UPDATE:"):
        vert_path = response.replace("UPDATE:", "").strip()
        vert_mode = "UPDATE"
        print(f"UPDATING EXISTING: {os.path.basename(vert_path)}")
    else:
        vert_mode = "NEW"
        print("CREATING NEW FROM TEMPLATE")

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
# OUTPUT FILE NAME / COPY TEMPLATE
# =========================

print("UI_STEP:Copying TOT VERT template")
sys.stdout.flush()

if vert_mode == "NEW":
    vert_path = make_output_path(
        calculations_folder, project_number,
        project_name_only, "TOT VERT XL"
    )
    shutil.copy2(template_path, vert_path)
    print(f"TOT VERT TEMPLATE COPIED: {os.path.basename(vert_path)}")
else:
    print(f"USING EXISTING VERT: {os.path.basename(vert_path)}")

# =========================
# OPEN BOTH — hidden until done
# =========================

print("UI_STEP:Copying cover data")
sys.stdout.flush()

# Clean up stale lock files before opening
cleanup_xl_locks(calculations_folder)

app = xw.App(visible=False)
app.display_alerts = False

# Enable macros — bypass security warning
try:
    app.api.AutomationSecurity = 1  # msoAutomationSecurityLow
except:
    pass

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
    description_ws = vert_wb.sheets["Description"]
    location_ws    = vert_wb.sheets["Location"]

    # Copy cover from TOT LAT
    vert_cover.range("A10").value = lat_cover.range("A10").value
    vert_cover.range("A11").value = lat_cover.range("A11").value
    vert_cover.range("A12").value = lat_cover.range("A12").value
    vert_cover.range("A13").value = lat_cover.range("A13").value
    vert_cover.range("D35").value = lat_cover.range("D35").value
    vert_cover.range("E37").value = project_number
    print("TOT LAT COVER DATA COPIED")

    # Project description — merge B4:F15 on Description sheet
    if good_description:
        try:
            desc_current = description_ws.range("B4").value
            if vert_mode == "UPDATE" and desc_current and str(desc_current).strip():
                print("DESCRIPTION ALREADY ON SHEET — SKIPPING")
            else:
                description_ws.activate()
                merge_range = description_ws.range("B4:F15")
                merge_range.api.Merge()
                merge_range.value = project_description
                merge_range.api.WrapText = True
                print("DESCRIPTION WRITTEN TO Description!B4:F15")
        except Exception as e:
            print(f"DESCRIPTION WRITE FAILED: {e}")

    # Hide Nevada Snow tab if it exists
    try:
        nevada_ws = vert_wb.sheets["Nevada Snow"]
        nevada_ws.api.Visible = False
        print("NEVADA SNOW TAB HIDDEN")
    except:
        pass

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

    # California Snow sheet — snow screenshot at A3, no resize
    # Skip if updating and picture already exists
    if not snow_screenshot:
        candidate = os.path.join(get_ui_folder(project_root), f"{project_number} - TOT Snow Load.png")
        if os.path.exists(candidate):
            snow_screenshot = candidate
            print(f"SNOW SCREENSHOT FOUND ON DISK: {os.path.basename(candidate)}")

    print("Inserting screenshots onto California Snow sheet...")
    cal_snow_ws.activate()

    if sheet_has_picture(cal_snow_ws) and vert_mode == "UPDATE":
        print("SNOW SCREENSHOT ALREADY ON SHEET — SKIPPING")
    elif snow_screenshot and os.path.exists(snow_screenshot):
        try:
            cal_snow_ws.pictures.add(
                os.path.abspath(snow_screenshot),
                top=cal_snow_ws.range("A3").top,
                left=cal_snow_ws.range("A3").left,
            )
            print("SNOW SCREENSHOT INSERTED")
        except Exception as e:
            print(f"SNOW SCREENSHOT INSERT FAILED: {e}")
    else:
        print("WARNING: Snow screenshot not found")

    # Location sheet — screenshot at A4, width 5.8 inches
    # Fall back to finding file on disk if INFO field is blank
    if not location_screenshot:
        candidate = os.path.join(get_ui_folder(project_root), f"{project_number} - Location.png")
        if os.path.exists(candidate):
            location_screenshot = candidate
            print(f"LOCATION SCREENSHOT FOUND ON DISK: {os.path.basename(candidate)}")

    print(f"Location screenshot path: {location_screenshot}")
    print("Inserting location screenshot...")
    location_ws.activate()
    if sheet_has_picture(location_ws) and vert_mode == "UPDATE":
        print("LOCATION SCREENSHOT ALREADY ON SHEET — SKIPPING")
    elif location_screenshot and os.path.exists(location_screenshot):
        try:
            pic = location_ws.pictures.add(
                os.path.abspath(location_screenshot),
                top=location_ws.range("A4").top,
                left=location_ws.range("A4").left,
            )
            # Set width to 5.8 inches (Excel uses points: 1 inch = 72 pts)
            pic.width  = 5.8 * 72
            # Height scales proportionally automatically
            print("LOCATION SCREENSHOT INSERTED")
        except Exception as e:
            print(f"LOCATION SCREENSHOT INSERT FAILED: {e}")
    else:
        print("WARNING: Location screenshot not found")

    # Snow load writeback — VERT Criteria D48 -> LAT W!M5
    try:
        roof_snow = criteria_ws.range("D48").value
        if roof_snow is not None:
            lat_w_ws = lat_wb.sheets["W"]
            lat_w_ws.range("M5").value = roof_snow
            print(f"ROOF SNOW LOAD -> LAT W!M5: {roof_snow}")
        else:
            print("WARNING: Criteria D48 is empty — LAT W!B6 not updated")
    except Exception as e:
        print(f"UI_LOG_WARNING_KEY:tot_lat:Snow load writeback to LAT W!M5 failed: {e}")

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

    # Close both — runner will reopen if user clicks Yes
    lat_wb.close()
    vert_wb.close()
    app.quit()

except Exception as e:
    try: lat_wb.close()
    except: pass
    try: vert_wb.close()
    except: pass
    app.quit()
    raise e

print("TOT VERT COMPLETE")
print("DONE")