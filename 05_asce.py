from playwright.sync_api import sync_playwright
from difflib import SequenceMatcher

import os
import re
import sys
from datetime import datetime

from config import (
    BASE_FOLDER,
    UI_SUBFOLDER,
    CALC_SUBFOLDER,
    YEAR_FOLDER_SUFFIX,
    HEADLESS,
)

# =========================
# PROJECT NUMBER
# =========================

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
    raise Exception("PROJECT FOLDER NOT FOUND")

# =========================
# FIND INFO FILE IN UI FOLDER
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

# =========================
# READ INFO FILE
# =========================

with open(info_path, "r", encoding="utf-8") as file:
    info_lines = file.readlines()

project_name    = ""
project_address = ""
city            = ""
state           = ""
zip_code        = ""
tot_status      = ""

for line in info_lines:
    if line.startswith("PROJECT_NAME="):
        project_name = line.replace("PROJECT_NAME=", "").strip()
    if line.startswith("PROJECT_ADDRESS="):
        project_address = line.replace("PROJECT_ADDRESS=", "").strip()
    if line.startswith("CITY="):
        city = line.replace("CITY=", "").strip()
    if line.startswith("STATE="):
        state = line.replace("STATE=", "").strip()
    if line.startswith("ZIP_CODE="):
        zip_code = line.replace("ZIP_CODE=", "").strip()
    if line.startswith("TOT="):
        tot_status = line.replace("TOT=", "").strip()

# =========================
# STOP IF TOT
# =========================

if tot_status == "Y":
    print("TOT PROJECT — USE TOT_ASCE.PY INSTEAD")
    sys.exit(0)

# =========================
# FOLDERS
# =========================

calculations_folder = os.path.join(project_root, CALC_SUBFOLDER)

# =========================
# CHECK IF ASCE PDF ALREADY EXISTS
# =========================

existing_asce = []
for file in os.listdir(calculations_folder):
    if (
        file.endswith(".pdf")
        and "ASCEDesignHazardsReport" in file
    ):
        existing_asce.append(file)

if existing_asce:
    # Ask user via UI signal
    print(f"UI_ASCE_EXISTS:{existing_asce[0]}")
    sys.stdout.flush()
    response = sys.stdin.readline().strip()
    if response == "SKIP":
        print(f"ASCE REPORT ALREADY EXISTS — SKIPPING")
        print("DONE")
        sys.exit(0)
    print("RE-RUNNING ASCE REPORT...")
    sys.stdout.flush()

# =========================
# TODAY DATE
# =========================

today_date = datetime.today().strftime("%m.%d.%y")
today_date = today_date.lstrip("0").replace(".0", ".")

# =========================
# FINAL PDF NAME
# =========================

final_pdf_name = (
    f"{project_number} {project_name}"
    f" - ASCEDesignHazardsReport"
    f" - {today_date}.pdf"
)

final_pdf_path = os.path.join(calculations_folder, final_pdf_name)

# =========================
# CLEAN ADDRESS FUNCTION
# =========================

def clean_address(text):
    text = text.lower()
    replacements = {
        "street": "st", "avenue": "ave",
        "road": "rd", "drive": "dr",
        "lane": "ln", "court": "ct",
        "boulevard": "blvd", "place": "pl",
        "california": "ca", "nevada": "nv"
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"[^a-z0-9 ]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

# =========================
# PLAYWRIGHT
# =========================

print("UI_STEP:Opening ASCE website")
sys.stdout.flush()

if HEADLESS:
    print('Running ASCE in background...')
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
    context = browser.new_context(accept_downloads=True)
    page    = context.new_page()

    page.goto("https://ascehazardtool.org/", timeout=120000)
    print("WEBSITE OPENED")
    page.wait_for_timeout(3000)

    # Close ASCE popup
    try:
        page.locator(
            "#welcomePopup > div.popup-header.blue"
            ".darken-3.welcome-header > "
            "span.details-popup-close-icon"
        ).click(force=True)
        print("ASCE POPUP CLOSED")
    except:
        print("ASCE POPUP NOT FOUND")

    page.wait_for_timeout(1000)

    # Close cookie popup
    try:
        page.locator("button:has-text('Got it')").click(force=True)
        print("COOKIE POPUP CLOSED")
    except:
        print("COOKIE POPUP NOT FOUND")

    # =========================
    # BUILD SEARCH ADDRESS
    # =========================

    print("UI_STEP:Entering address")
    sys.stdout.flush()

    search_address = project_address
    if city:
        search_address += f", {city}"
    if state:
        search_address += f", {state}"
    if zip_code:
        search_address += f" {zip_code}"

    print(f"FULL SEARCH ADDRESS: {search_address}")

    address_box = page.locator("#geocoder_input")
    address_box.click(force=True)
    address_box.fill(search_address)
    print("ADDRESS ENTERED")

    page.wait_for_timeout(3000)

    target_compare = clean_address(search_address)
    print(f"TARGET ADDRESS: {target_compare}")

    # =========================
    # KEYBOARD DROPDOWN SEARCH
    # =========================

    matched = False

    for i in range(8):
        address_box.press("ArrowDown")
        page.wait_for_timeout(700)

        current_value  = address_box.input_value()
        cleaned_result = clean_address(current_value)

        similarity = SequenceMatcher(
            None, target_compare, cleaned_result
        ).ratio()

        similarity_percent = round(similarity * 100, 1)
        print(f"DROPDOWN OPTION {i + 1}: {similarity_percent}% match")

        if similarity >= 0.90:
            matched = True
            print("MATCH FOUND")
            address_box.press("Enter")
            print("MATCHING ADDRESS SELECTED")
            break

    if not matched:
        raise Exception("NO MATCHING ADDRESS FOUND IN DROPDOWN")

    page.wait_for_timeout(4000)

    resolved_text = page.locator("#geocoder_input").input_value()
    print(f"RESOLVED ADDRESS: {resolved_text}")

    final_compare    = clean_address(resolved_text)
    final_similarity = SequenceMatcher(
        None, target_compare, final_compare
    ).ratio()
    final_percent = round(final_similarity * 100, 1)
    print(f"FINAL MATCH: {final_percent}%")

    if final_similarity < 0.90:
        raise Exception("FINAL ADDRESS VALIDATION FAILED")

    # =========================
    # SELECT CRITERIA
    # =========================

    print("UI_STEP:Selecting criteria")
    sys.stdout.flush()

    page.locator("#risk-level-selector").select_option("II")
    print("RISK CATEGORY II SELECTED")

    page.wait_for_timeout(1000)

    page.locator(
        "#criteria > div.criteria-container__content"
        ".white.margin--small > div:nth-child(4) > "
        "div.criteria-title-item > a"
    ).click(force=True)
    print("SELECT ALL CLICKED")

    page.wait_for_timeout(1000)

    page.locator("text=View Results").click(force=True)
    print("VIEW RESULTS CLICKED")

    # =========================
    # WAIT FOR RESULTS
    # =========================

    print("Waiting for results page...")
    page.wait_for_timeout(10000)

    page.wait_for_selector("text=Full Report", timeout=240000)
    print("FULL REPORT BUTTON FOUND")

    # =========================
    # DOWNLOAD REPORT
    # =========================

    print("UI_STEP:Downloading report")
    sys.stdout.flush()

    with page.expect_download(timeout=240000) as download_info:
        page.get_by_text("Full Report", exact=True).click(force=True)

    download = download_info.value
    print("DOWNLOAD COMPLETE")

    # =========================
    # SAVE PDF
    # =========================

    print("UI_STEP:Saving PDF")
    sys.stdout.flush()

    base_name          = os.path.splitext(final_pdf_name)[0]
    extension          = ".pdf"
    counter            = 2
    new_final_pdf_path = final_pdf_path

    while os.path.exists(new_final_pdf_path):
        new_final_pdf_path = os.path.join(
            calculations_folder,
            f"{base_name} ({counter}){extension}"
        )
        counter += 1

    download.save_as(new_final_pdf_path)
    print(f"PDF SAVED: {new_final_pdf_path}")

print('ASCE COMPLETE')
print('DONE')