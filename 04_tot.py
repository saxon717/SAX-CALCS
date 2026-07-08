from playwright.sync_api import sync_playwright
import os
import sys
import time
import re

from config import (
    find_project,
    get_project_name,
    get_ui_folder,
    read_info,
    update_info,
    TOT_WEBSITE,
    HEADLESS,
    YEAR_FOLDER_SUFFIX,
)

project_number = sys.argv[1]
force_rerun    = len(sys.argv) > 2 and sys.argv[2] == "--force"

# =========================
# FIND PROJECT
# =========================

print("UI_STEP:Reading INFO file")
sys.stdout.flush()

project_root, project_folder_name = find_project(project_number)
if not project_root:
    raise Exception("PROJECT NOT FOUND")

# =========================
# FIND INFO FILE
# =========================

ui_folder = get_ui_folder(project_root)

info_data, info_path = read_info(project_root, project_number)
if not info_path:
    raise Exception("INFO FILE NOT FOUND")

print("INFO FILE FOUND")

project_address   = info_data.get("PROJECT_ADDRESS", "")
verified_apn      = info_data.get("VERIFIED_APN", "")
existing_tot      = info_data.get("TOT", "")
existing_snow     = info_data.get("TOT_SNOW_LOAD", "")
existing_snow_png = info_data.get("TOT_SNOW_SCREENSHOT", "")
existing_snow_png = info_data.get("TOT_SNOW_SCREENSHOT", "")

# =========================
# SKIP IF ALREADY CONFIRMED
# =========================

if existing_tot in ("Y", "N") and not force_rerun:
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
tot_elevation            = ""

if HEADLESS:
    print('Running TOT in background...')
def _run_browser(headless):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        return browser

if HEADLESS:
    print('Running in background...')
    sys.stdout.flush()

with sync_playwright() as p:
    try:
        browser = p.chromium.launch(headless=HEADLESS)
    except Exception:
        print('UI_LOG_WARNING:Headless failed — retrying with visible browser')
        sys.stdout.flush()
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
                    time.sleep(2)
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
                    time.sleep(6)

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

                        # Click next arrow — this navigates to snow load page
                        next_sel = (
                            "#map_root > div.esriPopupMobile > "
                            "div.sizer > div > div.titleButton.arrow"
                        )
                        clicked_next = False
                        try:
                            next_btn = page.locator(next_sel)
                            if next_btn.count() > 0:
                                next_btn.first.click(force=True)
                                print("NEXT BUTTON CLICKED — waiting for snow load page")
                                clicked_next = True
                            else:
                                next_btn = target_frame.locator(next_sel)
                                if next_btn.count() > 0:
                                    next_btn.first.click(force=True)
                                    print("NEXT BUTTON CLICKED (frame) — waiting for snow load page")
                                    clicked_next = True
                                else:
                                    print("NEXT BUTTON NOT FOUND")
                        except Exception as e:
                            print(f"NEXT BUTTON CLICK FAILED: {e}")

                        next_sel = (
                            "#map_root > div.esriPopupMobile > "
                            "div.sizer > div > div.titleButton.arrow"
                        )
                        clicked_next = False

                        try:
                            # Use JS click to bypass visibility check
                            result = target_frame.evaluate(f"""
                                var btn = document.querySelector("{next_sel.replace('"', "'")}");
                                if (btn) {{ btn.click(); true; }} else {{ false; }}
                            """)
                            if result:
                                print("NEXT BUTTON CLICKED (JS — frame)")
                                clicked_next = True
                            else:
                                # Try on main page
                                result = page.evaluate(f"""
                                    var btn = document.querySelector("{next_sel.replace('"', "'")}");
                                    if (btn) {{ btn.click(); true; }} else {{ false; }}
                                """)
                                if result:
                                    print("NEXT BUTTON CLICKED (JS — page)")
                                    clicked_next = True
                                else:
                                    print("NEXT BUTTON NOT FOUND IN DOM")
                        except Exception as e:
                            print(f"NEXT BUTTON JS CLICK FAILED: {e}")

                        if clicked_next:
                            time.sleep(2)

                            # Data and popup are in the same frame
                            try:
                                target_frame.wait_for_selector(".esriViewPopup", timeout=6000)
                                print("POPUP LOADED IN FRAME")

                                # Extract data from table
                                attr_names  = target_frame.locator(".attrName").all_inner_texts()
                                attr_values = target_frame.locator(".attrValue").all_inner_texts()
                                attrs = dict(zip(
                                    [n.strip().upper() for n in attr_names],
                                    [v.strip() for v in attr_values]
                                ))
                                print(f"POPUP DATA: {attrs}")

                                for key in attrs:
                                    if "SNOWLOAD" in key or "SNOW LOAD" in key:
                                        tot_snow_load = attrs[key].replace(",", "")
                                        print(f"SNOW LOAD EXTRACTED: {tot_snow_load} PSF")
                                        break

                                for key in attrs:
                                    if "ELEVATION" in key:
                                        tot_elevation = attrs[key].replace(",", "")
                                        print(f"ELEVATION EXTRACTED: {tot_elevation} FT")
                                        break

                                # Screenshot full popup — blue bar + data + dots
                                try:
                                    # Get bounding boxes and clip
                                    bar  = target_frame.locator("body > div:nth-child(11) > div > div > div.esriMobileNavigationItem.center").first
                                    data = target_frame.locator("body > div:nth-child(12)").first
                                    bar_box  = bar.bounding_box()
                                    data_box = data.bounding_box()
                                    if bar_box and data_box:
                                        full_width = max(bar_box["width"], data_box["width"])
                                        clip = {
                                            "x":      min(bar_box["x"], data_box["x"]),
                                            "y":      bar_box["y"],
                                            "width":  int(full_width * 2 / 5),
                                            "height": (data_box["y"] + data_box["height"]) - bar_box["y"],
                                        }
                                        page.screenshot(path=snow_screenshot_path, clip=clip)
                                    else:
                                        page.screenshot(path=snow_screenshot_path, full_page=False)

                                    # Crop whitespace below three dots
                                    try:
                                        from PIL import Image
                                        img    = Image.open(snow_screenshot_path).convert("RGB")
                                        bottom = 0
                                        for y in range(img.height - 1, 0, -1):
                                            row = [img.getpixel((x, y)) for x in range(img.width)]
                                            if any(r < 245 or g < 245 or b < 245 for r, g, b in row):
                                                bottom = y + 15
                                                break
                                        if bottom > 0:
                                            img = img.crop((0, 0, img.width, min(bottom, img.height)))
                                            img.save(snow_screenshot_path)
                                            print(f"SNOW SCREENSHOT CROPPED AND SAVED: {snow_screenshot_path}")
                                        else:
                                            print(f"SNOW SCREENSHOT SAVED: {snow_screenshot_path}")
                                    except Exception as ce:
                                        print(f"CROP SKIPPED: {ce}")
                                        print(f"SNOW SCREENSHOT SAVED: {snow_screenshot_path}")
                                except Exception as e:
                                    print(f"POPUP SCREENSHOT FAILED: {e} — using full page")
                                    page.screenshot(path=snow_screenshot_path, full_page=False)
                                    print(f"FALLBACK SCREENSHOT SAVED: {snow_screenshot_path}")

                            except Exception as e:
                                print(f"FRAME DATA ERROR: {e} — using full page screenshot")
                                try:
                                    page.screenshot(path=snow_screenshot_path, full_page=False)
                                    print(f"FALLBACK SCREENSHOT SAVED: {snow_screenshot_path}")
                                except Exception as e2:
                                    print(f"SCREENSHOT FAILED: {e2}")
                        else:
                            print("WARNING: Could not click next button — skipping screenshot and data")

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

update_info(info_path, project_root, {
    "TOT":                   tot_status,
    "VERIFIED_PROJECT_ADDRESS": verified_project_address,
    "TOT_SNOW_LOAD":         tot_snow_load,
    "ELEVATION":             tot_elevation,
    "TOT_SNOW_SCREENSHOT":   snow_screenshot_path if os.path.exists(snow_screenshot_path) else "",
})

print(f"TOT STATUS UPDATED: {tot_status}")
if tot_snow_load:
    print(f"TOT SNOW LOAD: {tot_snow_load} PSF")
if verified_project_address:
    print(f"VERIFIED ADDRESS: {verified_project_address}")
if tot_status == "Y":
    print("TOT REMINDER: SNOW LOAD EXTRACTED AND SAVED TO INFO FILE")

print("DONE")