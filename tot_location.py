from playwright.sync_api import sync_playwright
import os
import sys
import time
import urllib.parse
import urllib.request
import json

from config import (
    BASE_FOLDER,
    UI_SUBFOLDER,
    YEAR_FOLDER_SUFFIX,
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

project_address = ""
city            = ""
state           = ""
zip_code        = ""

for line in info_lines:
    if line.startswith("PROJECT_ADDRESS="):
        project_address = line.replace("PROJECT_ADDRESS=", "").strip()
    if line.startswith("CITY="):
        city = line.replace("CITY=", "").strip()
    if line.startswith("STATE="):
        state = line.replace("STATE=", "").strip()
    if line.startswith("ZIP_CODE="):
        zip_code = line.replace("ZIP_CODE=", "").strip()

# =========================
# SKIP IF EXISTS
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

print(f"LOCATION: {search_address}")

# =========================
# GET COORDINATES VIA NOMINATIM (free, no API key)
# =========================

print("UI_STEP:Getting coordinates")
sys.stdout.flush()

lat = lng = None
try:
    encoded  = urllib.parse.quote(search_address)
    geo_url  = f"https://nominatim.openstreetmap.org/search?q={encoded}&format=json&limit=1"
    req      = urllib.request.Request(geo_url, headers={"User-Agent": "SAX/1.0"})
    response = urllib.request.urlopen(req, timeout=10)
    results  = json.loads(response.read())
    if results:
        lat = results[0]["lat"]
        lng = results[0]["lon"]
        print(f"COORDINATES: {lat}, {lng}")
    else:
        print("NO COORDINATES FOUND")
except Exception as e:
    print(f"GEOCODE ERROR: {e}")

if not lat or not lng:
    raise Exception("COULD NOT GET COORDINATES — cannot proceed")

# =========================
# OPEN GOOGLE MAPS SATELLITE DIRECTLY
# =========================

print("UI_STEP:Opening Google Maps")
sys.stdout.flush()

encoded_addr = urllib.parse.quote(search_address)
# Build satellite URL directly with pin + coords + zoom
maps_url = (
    f"https://www.google.com/maps/search/{encoded_addr}/"
    f"@{lat},{lng},18z"
    f"/data=!3m1!1e3"
)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page    = browser.new_page(viewport={"width": 1280, "height": 900})

    try:
        page.goto(maps_url, wait_until="domcontentloaded", timeout=30000)
        print("SATELLITE MAP OPENED")

        # Accept cookies if prompted
        try:
            page.locator('button:has-text("Accept all"), form[action*="consent"] button').first.click()
        except:
            pass

        # Wait for map canvas to render
        try:
            page.wait_for_selector("canvas", timeout=8000)
            time.sleep(1)
            print("MAP RENDERED")
        except:
            time.sleep(2)

        # Close left panel
        try:
            page.evaluate("""
                var btn = document.querySelector(
                    'body > div:nth-child(5) > div.lbMcOd.eZfyae.xcUKcd.y2Sqzf.Nkjr6c.K1N2o.y2iKwd.cSgCkb > div.UL7Qtf > div.g2LZJb > div > div > div.gYkzb > button > span'
                );
                if (btn) btn.click();
            """)
            time.sleep(0.5)
            print("LEFT PANEL CLOSED")
        except Exception as e:
            print(f"PANEL CLOSE: {e}")

        # Short wait for panel animation then screenshot
        time.sleep(1)

        print("UI_STEP:Taking screenshot")
        sys.stdout.flush()

        page.screenshot(path=screenshot_path, full_page=False)

        # Crop UI chrome
        try:
            from PIL import Image
            img     = Image.open(screenshot_path)
            w, h    = img.size
            cropped = img.crop((80, 55, w - 80, h - 130))
            cropped.save(screenshot_path)
            print(f"LOCATION SCREENSHOT SAVED: {screenshot_path}")
        except Exception as e:
            print(f"CROP SKIPPED: {e}")
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

print("LOCATION SCREENSHOT WRITTEN TO INFO")
print("DONE")