from playwright.sync_api import sync_playwright
import os
import sys
import time
import re

from config import (
    BASE_FOLDER,
    UI_SUBFOLDER,
    YEAR_FOLDER_SUFFIX,
    TOT_WEBSITE,
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

# =========================
# FIND INFO FILE
# =========================

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

project_address   = ""
verified_apn      = ""
existing_tot      = ""
existing_snow     = ""
existing_snow_png = ""

for line in info_lines:
    if line.startswith("PROJECT_ADDRESS="):
        project_address = line.replace("PROJECT_ADDRESS=", "").strip()
    if line.startswith("VERIFIED_APN="):
        verified_apn = line.replace("VERIFIED_APN=", "").strip()
    if line.startswith("TOT="):
        existing_tot = line.replace("TOT=", "").strip()
    if line.startswith("TOT_SNOW_LOAD="):
        existing_snow = line.replace("TOT_SNOW_LOAD=", "").strip()
    if line.startswith("TOT_SNOW_SCREENSHOT="):
        existing_snow_png = line.replace("TOT_SNOW_SCREENSHOT=", "").strip()

# =========================
# SKIP IF ALREADY CONFIRMED
# =========================

if existing_tot in ("Y", "N"):
    label = "TOT (Town of Truckee)" if existing_tot == "Y" else "NOT TOT"
    print(f"TOT already confirmed: {label} — skipping TOT check")
    print("DONE")
    sys.exit(0)

# =========================
# SEARCH VALUE
# =========================

if verified_apn:
    search_value = verified_apn
    print(f"USING VERIFIED APN: {search_value}")
else:
    search_value = project_address
    print(f"USING PROJECT ADDRESS: {search_value}")

manual_payload_suffix = f"|{project_address}|{verified_apn}"

snow_screenshot_path = os.path.join(
    ui_folder, f"{project_number} - TOT Snow Load.png"
)

def is_close_match(typed, suggestion):
    typed      = typed.lower().strip()
    suggestion = suggestion.lower().strip()
    if suggestion.startswith(typed[:6]):
        return True
    typed_words = typed.split()
    return all(w in suggestion for w in typed_words if len(w) > 3)

def send_manual(msg):
    print(f"UI_TOT_MANUAL:{msg}{manual_payload_suffix}")
    sys.stdout.flush()
    resp = sys.stdin.readline().strip()
    return resp

# =========================
# OPEN TOT WEBSITE
# =========================

print("UI_STEP:Opening TOT website")
sys.stdout.flush()

tot_status               = ""
verified_project_address = ""
tot_snow_load            = ""

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page    = browser.new_page()

    try:
        page.goto(TOT_WEBSITE, wait_until="domcontentloaded", timeout=60000)
        print("WEBSITE OPENED")
        time.sleep(6)
    except Exception as e:
        print(f"SITE FAILED TO LOAD: {e}")
        tot_status = send_manual("TOT website failed to load.")
        try: browser.close()
        except: pass
        tot_status = tot_status or "N"

    if not tot_status:
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            time.sleep(2)
        except:
            print("SCROLL FAILED — continuing")

        print("UI_STEP:Searching address")
        sys.stdout.flush()

        try:
            target_frame = None
            for attempt in range(30):
                for frame in page.frames:
                    try:
                        if frame.locator('div.jimu-popup-action-btn').count() > 0:
                            target_frame = frame
                            break
                        if frame.locator('#esri_dijit_Search_0_input').count() > 0:
                            target_frame = frame
                            break
                    except:
                        pass
                if target_frame:
                    break
                time.sleep(1)

            if target_frame is None:
                tot_status = send_manual("TOT website frame not found.")
            else:
                # Close popup
                try:
                    popup_btn = target_frame.locator('div.jimu-popup-action-btn')
                    if popup_btn.count() > 0:
                        popup_btn.first.click(force=True, timeout=5000)
                        print("POPUP CLOSED")
                        time.sleep(1)
                except:
                    print("NO POPUP TO CLOSE")

                try:
                    target_frame.evaluate("window.scrollTo(0, 0)")
                    time.sleep(1)
                except:
                    pass

                # Type search
                search_success = False
                try:
                    target_frame.wait_for_selector(
                        '#esri_dijit_Search_0_input', timeout=20000
                    )
                    search_box = target_frame.locator('#esri_dijit_Search_0_input')
                    search_box.scroll_into_view_if_needed()
                    time.sleep(1)
                    search_box.click(force=True)
                    time.sleep(1)
                    search_box.type(search_value, delay=80)
                    print(f"TYPED: {search_value}")
                    time.sleep(3)
                    search_success = True
                except Exception as e:
                    print(f"SEARCH BOX ERROR: {e}")

                if not search_success:
                    tot_status = send_manual(
                        f"Could not interact with search box. "
                        f"Tried to search for '{search_value}'."
                    )
                else:
                    # Check suggestion
                    suggestion_text    = ""
                    clicked_suggestion = False
                    suggestion_sel = (
                        '.searchMenu li, '
                        '.esri-search__suggestions-list li, '
                        '[class*="suggest"] li, '
                        '[class*="search"] ul li'
                    )
                    try:
                        target_frame.wait_for_selector(suggestion_sel, timeout=5000)
                        suggestions = target_frame.locator(suggestion_sel)
                        if suggestions.count() > 0:
                            suggestion_text = suggestions.first.inner_text().strip()
                            print(f"SUGGESTION FOUND: {suggestion_text}")
                    except:
                        print("NO DROPDOWN SUGGESTION APPEARED")

                    if suggestion_text and is_close_match(search_value, suggestion_text):
                        try:
                            target_frame.locator(suggestion_sel).first.click(timeout=5000)
                            clicked_suggestion       = True
                            verified_project_address = suggestion_text
                            print(f"CLICKED SUGGESTION: {suggestion_text}")
                            time.sleep(1)
                        except Exception as e:
                            print(f"COULD NOT CLICK SUGGESTION: {e}")
                            target_frame.locator('#esri_dijit_Search_0_input').press("Enter")
                    else:
                        target_frame.locator('#esri_dijit_Search_0_input').press("Enter")
                        print("PRESSED ENTER")

                    print("UI_STEP:Detecting TOT status")
                    sys.stdout.flush()
                    time.sleep(10)

                    page_text = ""
                    try:
                        page_text = target_frame.locator("body").inner_text()
                    except Exception as e:
                        print(f"COULD NOT READ PAGE: {e}")

                    found_snowload  = "GROUND SNOWLOAD" in page_text.upper()
                    found_no_result = (
                        "no results" in page_text.lower()
                        or "there were no results" in page_text.lower()
                    )

                    if found_snowload:
                        tot_status = "Y"
                        print("TOT DETECTED: GROUND SNOWLOAD FOUND")

                        # Extract values from popup text
                        try:
                            for line in page_text.split("\n"):
                                clean = re.sub(r"\s+", " ", line).strip()
                                has_num    = any(c.isdigit() for c in clean)
                                has_street = any(
                                    w in clean.upper() for w in [
                                        "WAY","RD","ROAD","DR","DRIVE","LN","LANE",
                                        "CT","COURT","AVE","AVENUE","BLVD","CIR",
                                        "PLACE","PL","ST","STREET"
                                    ]
                                )
                                if has_num and has_street and len(clean) < 100:
                                    verified_project_address = clean
                                    break
                        except:
                            pass

                        # Extract snow load value
                        try:
                            snow_match = re.search(
                                r"GROUND SNOWLOAD\s*\(PSF\)\s*(\d+)",
                                page_text.upper()
                            )
                            if snow_match:
                                tot_snow_load = snow_match.group(1)
                                print(f"SNOW LOAD EXTRACTED: {tot_snow_load} PSF")
                            else:
                                print("WARNING: Could not extract snow load value")
                        except Exception as e:
                            print(f"SNOW LOAD EXTRACTION ERROR: {e}")

                        # Click the arrow to expand popup fully then screenshot
                        try:
                            expand_btn = target_frame.locator(
                                '[class*="next"], [class*="arrow"], '
                                '[title*="next"], [title*="Next"]'
                            )
                            if expand_btn.count() > 0:
                                expand_btn.first.click(force=True)
                                time.sleep(2)
                                print("POPUP EXPANDED")
                        except:
                            pass

                        # Take screenshot of popup area
                        try:
                            popup_el = target_frame.locator(
                                '[class*="popup"], [class*="infoWindow"], '
                                '[class*="esriPopup"]'
                            ).first
                            if popup_el.count() > 0:
                                popup_el.screenshot(path=snow_screenshot_path)
                            else:
                                # Fall back to full page screenshot
                                page.screenshot(
                                    path=snow_screenshot_path,
                                    full_page=False
                                )
                            print(f"SNOW SCREENSHOT SAVED: {snow_screenshot_path}")
                        except Exception as e:
                            print(f"SNOW SCREENSHOT FAILED: {e}")
                            try:
                                page.screenshot(
                                    path=snow_screenshot_path,
                                    full_page=False
                                )
                                print(f"FALLBACK SCREENSHOT SAVED: {snow_screenshot_path}")
                            except:
                                pass

                        # Address mismatch check
                        if (
                            verified_project_address
                            and verified_project_address.lower() != project_address.lower()
                        ):
                            print(f"UI_ADDRESS_MISMATCH:{project_address}|{verified_project_address}")
                            sys.stdout.flush()
                            resp = sys.stdin.readline().strip()
                            if resp != "Y":
                                verified_project_address = ""

                    elif found_no_result:
                        tot_status = "N"
                        print("TOT DETECTED: NO RESULTS — NOT TOT")

                    else:
                        msg = (
                            f"Search for '{search_value}' returned inconclusive results."
                        )
                        tot_status = send_manual(msg)

        except Exception as e:
            print(f"BROWSER CLOSED OR ERROR: {e}")
            if not tot_status:
                tot_status = send_manual(
                    "Browser was closed or an error occurred."
                )

        try:
            browser.close()
        except:
            pass

# =========================
# VALIDATE
# =========================

if tot_status not in ("Y", "N"):
    tot_status = "N"
    print("WARNING: TOT STATUS DEFAULTED TO N")

# =========================
# UPDATE INFO FILE
# =========================

print("UI_STEP:Updating INFO file")
sys.stdout.flush()

fields_to_update = {
    "TOT=":                  tot_status,
    "VERIFIED_PROJECT_ADDRESS=": verified_project_address,
    "TOT_SNOW_LOAD=":        tot_snow_load,
    "TOT_SNOW_SCREENSHOT=":  snow_screenshot_path if os.path.exists(snow_screenshot_path) else "",
}

updated = list(info_lines)
for key, val in fields_to_update.items():
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

print(f"TOT STATUS UPDATED: {tot_status}")
if tot_snow_load:
    print(f"TOT SNOW LOAD: {tot_snow_load} PSF")
if verified_project_address:
    print(f"VERIFIED ADDRESS: {verified_project_address}")
if tot_status == "Y":
    print("TOT REMINDER: SNOW LOAD EXTRACTED AND SAVED TO INFO FILE")

print("DONE")