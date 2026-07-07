from playwright.sync_api import sync_playwright
from difflib import SequenceMatcher
import os
import sys
import re
import time
import pdfplumber
from datetime import datetime

from config import (
    BASE_FOLDER,
    UI_SUBFOLDER,
    CALC_SUBFOLDER,
    YEAR_FOLDER_SUFFIX,
    SEISMIC_WEBSITE,
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
    raise Exception("PROJECT NOT FOUND")

project_name_only = (
    project_folder_name
    .replace(project_number, "")
    .strip().lstrip("-").strip()
)

# =========================
# FIND INFO FILE
# =========================

ui_folder           = os.path.join(project_root, UI_SUBFOLDER)
calculations_folder = os.path.join(project_root, CALC_SUBFOLDER)
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
seismic_done    = ""

for line in info_lines:
    if line.startswith("PROJECT_ADDRESS="):
        project_address = line.replace("PROJECT_ADDRESS=", "").strip()
    if line.startswith("CITY="):
        city = line.replace("CITY=", "").strip()
    if line.startswith("STATE="):
        state = line.replace("STATE=", "").strip()
    if line.startswith("ZIP_CODE="):
        zip_code = line.replace("ZIP_CODE=", "").strip()
    if line.startswith("SEISMIC_PDF_DONE="):
        seismic_done = line.replace("SEISMIC_PDF_DONE=", "").strip()

# Skip if already done
if seismic_done == "Y":
    print("Seismic data already collected — skipping")
    print("DONE")
    sys.exit(0)

search_address = project_address
if city:
    search_address += f", {city}"
if state:
    search_address += f", {state}"
if zip_code:
    search_address += f" {zip_code}"

print(f"SEISMIC SEARCH ADDRESS: {search_address}")

# =========================
# OUTPUT PDF NAME
# =========================

today      = datetime.now()
date_str   = f"{today.month}.{today.day}.{str(today.year)[2:]}"
pdf_name   = f"{project_number} {project_name_only} - SeismicDesignReport - {date_str}.pdf"
pdf_path   = os.path.join(calculations_folder, pdf_name)

# =========================
# OPEN SEISMIC WEBSITE
# =========================

print("UI_STEP:Opening seismic website")
sys.stdout.flush()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(accept_downloads=True)
    page    = context.new_page()

    try:
        page.goto(SEISMIC_WEBSITE, wait_until="domcontentloaded", timeout=60000)
        print("SEISMIC WEBSITE OPENED")
        time.sleep(4)

        # Select ASCE 7-16 using correct dropdown ID and value
        try:
            page.wait_for_selector('#dcrd', timeout=10000)
            page.select_option('#dcrd', value='asce7-16')
            print("ASCE 7-16 SELECTED")
            time.sleep(1)
        except Exception as e:
            print(f"ASCE 7-16 SELECT FAILED: {e}")

        # Enter address using correct class selectors
        try:
            page.wait_for_selector('.searchbox', timeout=10000)
            search_box = page.locator('.searchbox').first
            search_box.click(force=True)
            time.sleep(1)
            search_box.fill(search_address)
            print(f"TYPED: {search_address}")
            time.sleep(2)
            page.locator('.searchbutton').first.click(force=True)
            print("SEARCH SUBMITTED")
            time.sleep(6)
        except Exception as e:
            print(f"SEISMIC SEARCH ERROR: {e}")
            print("Please search manually and save the PDF")

        # Show popup asking user to save PDF and confirm
        print(f"UI_SEISMIC_MANUAL:{pdf_path}")
        sys.stdout.flush()
        response = sys.stdin.readline().strip()

        if response == "DONE":
            print("PDF CONFIRMED BY USER")
        else:
            print("SEISMIC STEP SKIPPED")
            try: browser.close()
            except: pass
            print("DONE")
            sys.exit(0)

    except Exception as e:
        print(f"SEISMIC WEBSITE ERROR: {e}")

    try:
        browser.close()
    except:
        pass

# =========================
# FIND SAVED PDF
# =========================

print("UI_STEP:Extracting seismic values")
sys.stdout.flush()

# Find most recent seismic PDF in calculations folder
seismic_pdf = ""
latest_time = 0

for file in os.listdir(calculations_folder):
    if (
        file.endswith(".pdf")
        and (
            "seismic" in file.lower()
            or "SeismicDesign" in file
        )
    ):
        full_path     = os.path.join(calculations_folder, file)
        modified_time = os.path.getmtime(full_path)
        if modified_time > latest_time:
            latest_time = modified_time
            seismic_pdf = full_path

if not seismic_pdf:
    print("WARNING: No seismic PDF found — values not extracted")
    print("DONE")
    sys.exit(0)

print(f"SEISMIC PDF FOUND: {seismic_pdf}")

# =========================
# EXTRACT VALUES FROM PDF
# =========================

ss_value         = ""
sms_value        = ""
sds_value        = ""
s1_value         = ""
sm1_value        = ""
sd1_value        = ""
seismic_category = ""

try:
    with pdfplumber.open(seismic_pdf) as pdf:
        # Try page 3 first (same as ASCE), fall back to page 1
        for page_num in [2, 0, 1]:
            if page_num >= len(pdf.pages):
                continue
            text  = pdf.pages[page_num].extract_text()
            if not text:
                continue
            lines = text.split("\n")
            for i, line in enumerate(lines):
                if "MS S" in line:
                    prev  = lines[i - 1].split()
                    sms_value = prev[2] if len(prev) > 2 else ""
                    ss_value  = prev[-1] if prev else ""
                if "M1 1" in line:
                    prev  = lines[i - 1].split()
                    sm1_value = prev[2] if len(prev) > 2 else ""
                    s1_value  = prev[-1] if prev else ""
                if "DS S30" in line:
                    prev  = lines[i - 1].split()
                    sds_value = prev[2] if len(prev) > 2 else ""
                if "D1" in line:
                    prev  = lines[i - 1].split()
                    sd1_value = prev[-1] if prev else ""
                if "Seismic Design Category" in line:
                    seismic_category = line.split(":")[-1].strip()
            if ss_value:
                break
except Exception as e:
    print(f"PDF EXTRACTION ERROR: {e}")

print(f"Ss={ss_value} Sms={sms_value} Sds={sds_value}")
print(f"S1={s1_value} Sm1={sm1_value} Sd1={sd1_value}")
print(f"Seismic Category={seismic_category}")

# =========================
# UPDATE INFO FILE
# =========================

print("UI_STEP:Updating INFO file")
sys.stdout.flush()

fields = {
    "SEISMIC_SS=":       ss_value,
    "SEISMIC_SMS=":      sms_value,
    "SEISMIC_SDS=":      sds_value,
    "SEISMIC_S1=":       s1_value,
    "SEISMIC_SM1=":      sm1_value,
    "SEISMIC_SD1=":      sd1_value,
    "SEISMIC_CATEGORY=": seismic_category,
    "SEISMIC_PDF_DONE=": "Y",
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

print("SEISMIC VALUES WRITTEN TO INFO FILE")
print("DONE")