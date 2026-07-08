from playwright.sync_api import sync_playwright
import os
import sys
import time
import urllib.parse
import urllib.request
import json

from config import (
    find_project,
    get_ui_folder,
    read_info,
    update_info,
    HEADLESS,
    YEAR_FOLDER_SUFFIX,
)

project_number = sys.argv[1]
project_root, project_folder_name = find_project(project_number)
if not project_root:
    raise Exception("PROJECT NOT FOUND")

ui_folder = get_ui_folder(project_root)
os.makedirs(ui_folder, exist_ok=True)

info_data, info_path = read_info(project_root, project_number)
if not info_path:
    raise Exception("INFO FILE NOT FOUND")

print("INFO FILE FOUND")

project_address = info_data.get("PROJECT_ADDRESS", "")
city = info_data.get("CITY", "")
state = info_data.get("STATE", "")
zip_code = info_data.get("ZIP_CODE", "")
location_png = info_data.get("LOCATION_SCREENSHOT", "")

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

def run_maps(headless):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
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

            return True

        except Exception as e:
            print(f"GOOGLE MAPS ERROR: {e}")
            return False
        finally:
            try:
                browser.close()
            except:
                pass


# Try headless first if enabled, fallback to visible
success = False
if HEADLESS:
    print("Running in background (headless)...")
    success = run_maps(headless=True)
    if not success:
        print("UI_LOG_WARNING:Headless failed — retrying with visible browser")
        sys.stdout.flush()
        print("WARNING: Headless mode failed — retrying with visible browser")
        success = run_maps(headless=False)
else:
    success = run_maps(headless=False)

if not success:
    raise Exception("GOOGLE MAPS SCREENSHOT FAILED")

# =========================
# UPDATE INFO FILE
# =========================

print("UI_STEP:Updating INFO file")
sys.stdout.flush()

png_val = screenshot_path if os.path.exists(screenshot_path) else ""
update_info(info_path, project_root, {"LOCATION_SCREENSHOT": png_val})

print("LOCATION SCREENSHOT WRITTEN TO INFO")
print("DONE")