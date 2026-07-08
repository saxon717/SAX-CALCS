from playwright.sync_api import sync_playwright
import os
import sys
import time
import re
import pdfplumber

from config import (
    find_project,
    get_project_name,
    get_ui_folder,
    get_calc_folder,
    read_info,
    update_info,
    make_output_path,
    SEISMIC_WEBSITE,
    HEADLESS,
    YEAR_FOLDER_SUFFIX,
)

project_number = sys.argv[1]
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
os.makedirs(ui_folder, exist_ok=True)

info_data, info_path = read_info(project_root, project_number)
if not info_path:
    raise Exception("INFO FILE NOT FOUND")

print("INFO FILE FOUND")

project_address = info_data.get("PROJECT_ADDRESS", "")
city = info_data.get("CITY", "")
state = info_data.get("STATE", "")
zip_code = info_data.get("ZIP_CODE", "")
seismic_done = info_data.get("SEISMIC_PDF_DONE", "")

# =========================
# PDF NAME
# =========================

from datetime import datetime
today    = datetime.now()
date_str = f"{today.month}.{today.day}.{str(today.year)[2:]}"
pdf_name = f"{project_number} {project_name_only} - SeismicDesignReport - {date_str}.pdf"
pdf_path = os.path.join(calculations_folder, pdf_name)

# =========================
# OPEN SEISMIC WEBSITE — always headless for page.pdf()
# =========================

print("UI_STEP:Opening seismic website")
sys.stdout.flush()

if HEADLESS:
    print("Running in background...")
    sys.stdout.flush()

with sync_playwright() as p:
    try:
        browser = p.chromium.launch(headless=True)
    except Exception:
        print("UI_LOG_WARNING:Headless failed — retrying with visible browser")
        sys.stdout.flush()
        browser = p.chromium.launch(headless=False)

    context = browser.new_context(accept_downloads=True)
    page    = context.new_page()

    try:
        page.goto(SEISMIC_WEBSITE, wait_until="domcontentloaded", timeout=60000)
        print("SEISMIC WEBSITE OPENED")
        time.sleep(3)

        # Select ASCE 7-16
        try:
            page.wait_for_selector('#dcrd', timeout=10000)
            page.select_option('#dcrd', value='asce7-16')
            print("ASCE 7-16 SELECTED")
            time.sleep(1)
        except Exception as e:
            print(f"ASCE 7-16 SELECT FAILED: {e}")

        # Enter address
        try:
            page.wait_for_selector('.searchbox', timeout=10000)
            search_box = page.locator('.searchbox').first
            search_box.click(force=True)
            time.sleep(0.5)
            search_box.fill(search_address)
            print(f"TYPED: {search_address}")
            time.sleep(1)
            page.locator('.searchbutton').first.click(force=True)
            print("SEARCH SUBMITTED")
            time.sleep(8)
        except Exception as e:
            print(f"SEISMIC SEARCH ERROR: {e}")

        # Save PDF
        try:
            print("Saving seismic PDF...")
            sys.stdout.flush()
            time.sleep(3)
            page.pdf(
                path=pdf_path,
                format="Letter",
                print_background=True
            )
            print(f"SEISMIC PDF SAVED: {pdf_path}")
            sys.stdout.flush()
        except Exception as e:
            print(f"PDF SAVE ERROR: {e}")

    except Exception as e:
        print(f"SEISMIC WEBSITE ERROR: {e}")

    try:
        browser.close()
    except:
        pass

# =========================
# EXTRACT VALUES FROM PDF
# =========================

print("UI_STEP:Extracting seismic values")
sys.stdout.flush()

seismic_pdf = ""
latest_time = 0

for file in os.listdir(calculations_folder):
    if (
        file.endswith(".pdf")
        and "SeismicDesignReport" in file
        and not file.startswith("~$")
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

# Extract all text from PDF
full_text = ""
try:
    with pdfplumber.open(seismic_pdf) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                full_text += t + "\n"
except Exception as e:
    print(f"PDF READ ERROR: {e}")

# Helper to extract value after label
def extract_val(text, label):
    pattern = rf"{re.escape(label)}\s+([\d\.]+)"
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return ""

def extract_text_val(text, label):
    pattern = rf"{re.escape(label)}\s+([^\n]+)"
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        return m.group(1).strip().split()[0]
    return ""

ss_value      = extract_val(full_text, "SS")
s1_value      = extract_val(full_text, "S1")
fa_value      = extract_val(full_text, "Fa")
tl_value      = extract_val(full_text, "TL")
sms_value     = extract_val(full_text, "SMS")
sds_value     = extract_val(full_text, "SDS")
risk_category = extract_text_val(full_text, "Risk Category")
site_class    = extract_text_val(full_text, "Site Class")

# Defaults
if not fa_value:
    fa_value = "1.2"
if not risk_category:
    risk_category = "II"
if not site_class:
    site_class = "D"
# Extract just the letter for site class
site_class = site_class[0] if site_class else "D"

print(f"Ss={ss_value} S1={s1_value} Fa={fa_value} TL={tl_value}")
print(f"Sms={sms_value} Sds={sds_value}")
print(f"Risk Category={risk_category} Site Class={site_class}")

# =========================
# UPDATE INFO FILE
# =========================

print("UI_STEP:Updating INFO file")
sys.stdout.flush()

fields = {
    "SEISMIC_SS=":       ss_value,
    "SEISMIC_S1=":       s1_value,
    "SEISMIC_FA=":       fa_value,
    "SEISMIC_TL=":       tl_value,
    "SEISMIC_SMS=":      sms_value,
    "SEISMIC_SDS=":      sds_value,
    "SEISMIC_RISK=":     risk_category,
    "SEISMIC_CLASS=":    site_class,
    "SEISMIC_PDF_DONE=": "Y",
}

update_info(info_path, project_root, {k.rstrip('='): v for k, v in fields.items()})

print("SEISMIC VALUES WRITTEN TO INFO FILE")
print("DONE")