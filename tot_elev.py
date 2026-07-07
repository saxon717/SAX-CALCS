from playwright.sync_api import sync_playwright
import os
import sys
import time
import re

from config import (
    BASE_FOLDER,
    UI_SUBFOLDER,
    YEAR_FOLDER_SUFFIX,
    ELEVATION_WEBSITE,
)

project_number = sys.argv[1]
year_prefix    = project_number[:2]
year_folder    = os.path.join(BASE_FOLDER, f"{year_prefix}{YEAR_FOLDER_SUFFIX}")

# =========================
# FIND PROJECT
# =========================

print("UI_STEP:Reading INFO file")
sys.stdout.flush()

project_root = ""
for folder in os.listdir(year_folder):
    if folder.startswith(project_number):
        project_root = os.path.join(year_folder, folder)
        break

if project_root == "":
    raise Exception("PROJECT NOT FOUND")

ui_folder = os.path.join(project_root, UI_SUBFOLDER)
os.makedirs(ui_folder, exist_ok=True)

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

project_address    = ""
city               = ""
state              = ""
zip_code           = ""
elevation          = ""
elevation_png      = ""

for line in info_lines:
    if line.startswith("PROJECT_ADDRESS="):
        project_address = line.replace("PROJECT_ADDRESS=", "").strip()
    if line.startswith("CITY="):
        city = line.replace("CITY=", "").strip()
    if line.startswith("STATE="):
        state = line.replace("STATE=", "").strip()
    if line.startswith("ZIP_CODE="):
        zip_code = line.replace("ZIP_CODE=", "").strip()
    if line.startswith("ELEVATION="):
        elevation = line.replace("ELEVATION=", "").strip()
    if line.startswith("ELEVATION_SCREENSHOT="):
        elevation_png = line.replace("ELEVATION_SCREENSHOT=", "").strip()

# =========================
# SKIP IF SCREENSHOT ALREADY EXISTS
# =========================

screenshot_path = os.path.join(ui_folder, f"{project_number} - Elevation.png")

if os.path.exists(screenshot_path) and elevation:
    print(f"Elevation screenshot already exists: {os.path.basename(screenshot_path)}")
    print(f"UI_ELEV_EXISTS:{screenshot_path}")
    sys.stdout.flush()
    response = sys.stdin.readline().strip()
    if response == "SKIP":
        print("ELEVATION — SKIPPING")
        print("DONE")
        sys.exit(0)
    print("RE-RUNNING ELEVATION...")

search_address = project_address
if city:
    search_address += f", {city}"
if state:
    search_address += f", {state}"
if zip_code:
    search_address += f" {zip_code}"

print(f"SEARCHING ELEVATION FOR: {search_address}")

# =========================
# OPEN ELEVATION WEBSITE
# =========================

print("UI_STEP:Opening elevation website")
sys.stdout.flush()

elevation_value = ""

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page    = browser.new_page(viewport={"width": 1280, "height": 900})

    try:
        page.goto(ELEVATION_WEBSITE, wait_until="domcontentloaded", timeout=60000)
        print("ELEVATION WEBSITE OPENED")
        time.sleep(4)

        # Search for address
        try:
            search_sel = (
                'input[type="text"], input[placeholder*="address"], '
                'input[placeholder*="Address"], #search, #pac-input, '
                'input[class*="search"]'
            )
            page.wait_for_selector(search_sel, timeout=10000)
            search_box = page.locator(search_sel).first
            search_box.click(force=True)
            time.sleep(1)
            search_box.fill(search_address)
            print(f"TYPED: {search_address}")
            time.sleep(3)

            # Click first autocomplete suggestion if available
            try:
                suggestion_sel = '.pac-item, [class*="suggestion"], [class*="autocomplete"] li'
                page.wait_for_selector(suggestion_sel, timeout=3000)
                page.locator(suggestion_sel).first.click()
                print("SUGGESTION CLICKED")
            except:
                search_box.press("Enter")
                print("ENTER PRESSED")

            time.sleep(5)

        except Exception as e:
            print(f"SEARCH ERROR: {e}")

        # Extract elevation value from page
        try:
            body_text = page.locator("body").inner_text()
            match = re.search(
                r"([\d,]+)\s*(ft|feet|m|meters)\b",
                body_text,
                re.IGNORECASE
            )
            if match:
                elevation_value = f"{match.group(1)} {match.group(2)}"
                print(f"ELEVATION FOUND: {elevation_value}")
            else:
                print("WARNING: Elevation value not auto-detected")
        except Exception as e:
            print(f"ELEVATION EXTRACTION ERROR: {e}")

        # Screenshot just the result area
        try:
            result_sel = (
                '[class*="elevation"], [id*="elevation"], '
                '[class*="result"], h1, h2'
            )
            result_el = page.locator(result_sel).first
            if result_el.is_visible():
                # Capture a region around the result
                page.screenshot(path=screenshot_path, clip={
                    "x": 0, "y": 0, "width": 500, "height": 400
                })
            else:
                page.screenshot(path=screenshot_path, full_page=False)
            print(f"SCREENSHOT SAVED: {screenshot_path}")
        except Exception as e:
            print(f"SCREENSHOT ERROR: {e}")
            try:
                page.screenshot(path=screenshot_path, full_page=False)
                print(f"FALLBACK SCREENSHOT SAVED: {screenshot_path}")
            except:
                pass

    except Exception as e:
        print(f"ELEVATION WEBSITE ERROR: {e}")

    try:
        browser.close()
    except:
        pass

# =========================
# UPDATE INFO FILE
# =========================

print("UI_STEP:Updating INFO file")
sys.stdout.flush()

fields = {
    "ELEVATION=":             elevation_value,
    "ELEVATION_SCREENSHOT=":  screenshot_path if os.path.exists(screenshot_path) else "",
}

updated = list(info_lines)
for key, val in fields.items():
    found = False
    for i, line in enumerate(updated):
        if line.startswith(key):
            updated[i] = f"{key}{val}\n"
            found = True
            break
    if not found:
        updated.append(f"{key}{val}\n")

with open(info_path, "w", encoding="utf-8") as f:
    f.writelines(updated)

print(f"ELEVATION WRITTEN TO INFO: {elevation_value}")
print("DONE")