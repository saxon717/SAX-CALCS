from playwright.sync_api import sync_playwright
import os
import sys
import time

from config import (
    BASE_FOLDER,
    UI_SUBFOLDER,
    YEAR_FOLDER_SUFFIX,
)

GOOGLE_MAPS_URL = "https://www.google.com/maps"

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
location_png       = ""

for line in info_lines:
    if line.startswith("PROJECT_ADDRESS="):
        project_address = line.replace("PROJECT_ADDRESS=", "").strip()
    if line.startswith("CITY="):
        city = line.replace("CITY=", "").strip()
    if line.startswith("STATE="):
        state = line.replace("STATE=", "").strip()
    if line.startswith("ZIP_CODE="):
        zip_code = line.replace("ZIP_CODE=", "").strip()
    if line.startswith("LOCATION_SCREENSHOT="):
        location_png = line.replace("LOCATION_SCREENSHOT=", "").strip()

# =========================
# SKIP IF SCREENSHOT ALREADY EXISTS
# =========================

screenshot_path = os.path.join(ui_folder, f"{project_number} - Location.png")

if os.path.exists(screenshot_path):
    print(f"Location screenshot already exists: {os.path.basename(screenshot_path)}")
    print(f"UI_LOCATION_EXISTS:{screenshot_path}")
    sys.stdout.flush()
    response = sys.stdin.readline().strip()
    if response == "SKIP":
        print("LOCATION SCREENSHOT — SKIPPING")
        print("DONE")
        sys.exit(0)
    print("RE-RUNNING LOCATION SCREENSHOT...")

search_address = project_address
if city:
    search_address += f", {city}"
if state:
    search_address += f", {state}"
if zip_code:
    search_address += f" {zip_code}"

print(f"SEARCHING LOCATION FOR: {search_address}")

# =========================
# OPEN GOOGLE MAPS SATELLITE
# =========================

print("UI_STEP:Opening Google Maps")
sys.stdout.flush()

import urllib.parse
encoded = urllib.parse.quote(search_address)
maps_url = f"https://www.google.com/maps/search/{encoded}/@?entry=ttu"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page    = browser.new_page(viewport={"width": 1280, "height": 900})

    try:
        page.goto(maps_url, wait_until="domcontentloaded", timeout=60000)
        print("GOOGLE MAPS OPENED")
        time.sleep(5)

        # Accept cookies if prompted
        try:
            page.locator('button:has-text("Accept all"), button:has-text("Accept"), [aria-label*="Accept"]').first.click(force=True)
            time.sleep(1)
        except:
            pass

        print("UI_STEP:Switching to satellite view")
        sys.stdout.flush()

        # Switch to satellite view
        try:
            # Click the layers button
            layers_btn = page.locator(
                '[aria-label="Layers"], button:has-text("Layers"), '
                '[data-value="satellite"], [jsaction*="satellite"]'
            ).first
            layers_btn.click(force=True)
            time.sleep(2)

            # Click satellite option
            sat_btn = page.locator(
                '[aria-label*="Satellite"], [data-value="satellite"], '
                'img[alt*="Satellite"], [jsaction*="satellite"]'
            ).first
            sat_btn.click(force=True)
            time.sleep(3)
            print("SATELLITE VIEW ACTIVATED")
        except Exception as e:
            print(f"SATELLITE SWITCH FAILED: {e} — using current view")

        # Set zoom — look for zoom controls
        try:
            # Zoom in a bit for neighbourhood level
            zoom_in = page.locator('[aria-label="Zoom in"], button[title="Zoom in"]').first
            for _ in range(2):
                zoom_in.click(force=True)
                time.sleep(0.8)
            print("ZOOM ADJUSTED")
        except:
            pass

        time.sleep(3)

        print("UI_STEP:Taking screenshot")
        sys.stdout.flush()

        # Hide UI elements for cleaner screenshot then take it
        try:
            page.evaluate("""
                document.querySelectorAll(
                    '.searchbox, #searchbox, #omnibox-container, '
                    + '.widget-scene-canvas, [class*="search-input"]'
                ).forEach(el => el.style.opacity = '0');
            """)
            time.sleep(1)
        except:
            pass

        page.screenshot(path=screenshot_path, full_page=False)
        print(f"LOCATION SCREENSHOT SAVED: {screenshot_path}")

    except Exception as e:
        print(f"GOOGLE MAPS ERROR: {e}")

    try:
        browser.close()
    except:
        pass

# =========================
# UPDATE INFO FILE
# =========================

print("UI_STEP:Updating INFO file")
sys.stdout.flush()

png_val = screenshot_path if os.path.exists(screenshot_path) else ""
updated = list(info_lines)
found   = False

for i, line in enumerate(updated):
    if line.startswith("LOCATION_SCREENSHOT="):
        updated[i] = f"LOCATION_SCREENSHOT={png_val}\n"
        found = True
        break

if not found:
    updated.append(f"LOCATION_SCREENSHOT={png_val}\n")

with open(info_path, "w", encoding="utf-8") as f:
    f.writelines(updated)

print(f"LOCATION SCREENSHOT WRITTEN TO INFO")
print("DONE")