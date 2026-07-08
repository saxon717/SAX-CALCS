import pdfplumber
import os
import re
import sys
import threading

from config import (
    find_project,
    get_project_name,
    get_ui_folder,
    get_calc_folder,
    find_info_file,
    write_info_lines,
    today_str,
    CONTRACT_SUBFOLDER,
)

project_number = sys.argv[1]

# =========================
# FIND PROJECT
# =========================

project_root, project_folder_name = find_project(project_number)
if not project_root:
    raise Exception("PROJECT NOT FOUND")

project_name    = get_project_name(project_folder_name, project_number)
ui_folder       = get_ui_folder(project_root)
contract_folder = os.path.join(project_root, CONTRACT_SUBFOLDER)

# =========================
# STEP 1 — CHECK FOR EXISTING INFO FILES
# =========================

print("UI_STEP:Checking for existing INFO files")
sys.stdout.flush()

import glob
existing_infos = sorted(
    [f for f in glob.glob(os.path.join(ui_folder, f"{project_number} INFO*.txt"))
     if not os.path.basename(f).startswith("~")],
    key=os.path.getmtime,
    reverse=True
)

print(f"SEARCHING UI FOLDER: {ui_folder}")
print(f"MATCHING INFO FILES: {len(existing_infos)}")
sys.stdout.flush()

info_path             = ""
existing_tot          = ""
existing_verified_apn = ""
existing_monday       = ""

if existing_infos:
    files_str = "|".join(existing_infos)
    print(f"UI_INFO_EXISTS:{files_str}")
    sys.stdout.flush()
    response = sys.stdin.readline().strip()

    if response == "SKIP":
        print("INFO FILE ALREADY EXISTS — SKIPPING")
        print("DONE")
        sys.exit()

    elif response.startswith("OVERWRITE"):
        # May include specific file path: OVERWRITE:/path/to/file.txt
        parts = response.split(":", 1)
        if len(parts) > 1 and os.path.exists(parts[1]):
            info_path = parts[1]
            print(f"OVERWRITING: {os.path.basename(info_path)}")
        else:
            info_path = existing_infos[-1]
            print("OVERWRITING OLDEST INFO FILE")
        try:
            for src_file in existing_infos:
                with open(src_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("TOT=") and not existing_tot:
                            existing_tot = line.replace("TOT=", "").strip()
                        if line.startswith("VERIFIED_APN=") and not existing_verified_apn:
                            existing_verified_apn = line.replace("VERIFIED_APN=", "").strip()
                        if line.startswith("MONDAY_UPLOADED=") and not existing_monday:
                            existing_monday = line.replace("MONDAY_UPLOADED=", "").strip()
        except:
            pass
    else:
        print("CREATING NEW INFO FILE")

# =========================
# STEP 2 — FIND CONTRACT PDF
# =========================

print("UI_STEP:Finding contract PDF")
sys.stdout.flush()

contract_pdf = ""
for file in os.listdir(contract_folder):
    if file.lower().endswith(".pdf"):
        contract_pdf = os.path.join(contract_folder, file)
        break

if not contract_pdf:
    raise Exception("NO CONTRACT PDF FOUND")

print("CONTRACT PDF FOUND")
sys.stdout.flush()

# =========================
# STEP 3 — READ PDF IN BACKGROUND
# =========================

pdf_text  = [""]
pdf_done  = threading.Event()
pdf_error = [""]

def read_pdf():
    try:
        text = ""
        with pdfplumber.open(contract_pdf) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
        pdf_text[0] = text
    except Exception as e:
        pdf_error[0] = str(e)
    finally:
        pdf_done.set()

threading.Thread(target=read_pdf, daemon=True).start()

print("UI_STEP:Reading PDF")
sys.stdout.flush()

print(f"UI_OPEN_PDF:{contract_pdf}")
sys.stdout.flush()

pdf_done.wait()

if pdf_error[0]:
    raise Exception(f"PDF READ FAILED: {pdf_error[0]}")

text = pdf_text[0]
print("Extracting PDF info...")
sys.stdout.flush()

# =========================
# PROJECT DESCRIPTION
# =========================

project_description = ""
if "Project Description" in text and "Scope" in text:
    description_lines = []
    capture = False
    for line in text.split("\n"):
        clean_line = line.strip()
        if "Project Description" in clean_line:
            capture = True
            continue
        if capture and "Scope" in clean_line:
            break
        if capture and clean_line:
            description_lines.append(clean_line)
    project_description = " ".join(description_lines)

project_description = re.sub(r"\s+", " ", project_description).strip()

# =========================
# CLEAN TEXT
# =========================

text        = re.sub(r"\(cid:\d+\)", "", text)
lines       = text.split("\n")
lower_lines = [line.lower().strip() for line in lines]

# =========================
# STEP 4 — EXTRACT ADDRESS
# =========================

print("UI_STEP:Extracting address")
sys.stdout.flush()

street_address         = ""
city                   = ""
state                  = ""
zip_code               = ""
county                 = ""
apn                    = ""
good_template          = False
manual_project_address = ""
apn_warning            = False

try:
    for i, line in enumerate(lower_lines):
        if "re:" in line:
            for j in range(i, min(i + 10, len(lines))):
                possible_address = lines[j].strip()
                has_number = any(char.isdigit() for char in possible_address)
                has_comma  = "," in possible_address
                if has_number and has_comma:
                    address_parts = [p.strip() for p in possible_address.split(",")]
                    if len(address_parts) >= 3:
                        street_address = address_parts[0]
                        city           = address_parts[1]
                        state_zip      = address_parts[2]
                        state_match    = re.search(r"\b[A-Z]{2}\b", state_zip)
                        zip_match      = re.search(r"\b\d{5}\b", state_zip)
                        if state_match:
                            state = state_match.group(0)
                        if zip_match:
                            zip_code = zip_match.group(0)
                        good_template = True
                        break
            if good_template:
                break
except Exception as e:
    print(f"ADDRESS EXTRACTION FAILED: {e}")

if not good_template:
    print("BAD TEMPLATE DETECTED")
    print(f"UI_BAD_TEMPLATE:{contract_pdf}")
    sys.stdout.flush()
    manual_address = sys.stdin.readline().strip()
    if not manual_address or manual_address == "CANCELLED":
        raise Exception("NO MANUAL ADDRESS ENTERED")
    street_address         = manual_address
    manual_project_address = manual_address

# =========================
# STEP 5 — EXTRACT APN
# =========================

print("UI_STEP:Extracting APN")
sys.stdout.flush()

for line in lines:
    lower_line = line.lower()
    if "county apn" in lower_line:
        if "placer" in lower_line:
            county = "PLACER"
        elif "nevada" in lower_line:
            county = "NEVADA"
        raw_apn_match = re.search(r"(\d[\d\-]{6,20}\d)", line)
        if raw_apn_match:
            raw_apn    = raw_apn_match.group(1)
            apn_digits = re.sub(r"\D", "", raw_apn)
            if len(apn_digits) >= 9:
                core_digits = apn_digits[:9]
                apn = f"{core_digits[0:3]}-{core_digits[3:6]}-{core_digits[6:9]}"
                if raw_apn != apn:
                    apn_warning = True
            else:
                print("WARNING: NOT ENOUGH DIGITS FOR APN")
        break

# =========================
# STEP 6 — EXTRACT CLIENT INFO
# =========================

print("UI_STEP:Extracting client info")
sys.stdout.flush()

client_names  = []
client_emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)
client_emails = list(dict.fromkeys(client_emails))

for i, line in enumerate(lines):
    lower_line = line.lower().strip()
    if "via e-mail:" in lower_line or "via email:" in lower_line:
        for j in range(i - 1, -1, -1):
            possible_name = lines[j].strip()
            if not possible_name:
                continue
            if "@" in possible_name or "proposal" in possible_name.lower() or "engineering" in possible_name.lower():
                continue
            split_names = re.split(r",|\+| and ", possible_name)
            for split_name in split_names:
                clean_name = split_name.strip()
                word_count = len(clean_name.split())
                if word_count >= 2 and word_count <= 5:
                    if any(char.isalpha() for char in clean_name):
                        client_names.append(clean_name.upper())
            break

client_names = list(dict.fromkeys(client_names))

client_name_1  = client_names[0]  if len(client_names)  >= 1 else ""
client_name_2  = client_names[1]  if len(client_names)  >= 2 else ""
client_email_1 = client_emails[0] if len(client_emails) >= 1 else ""
client_email_2 = client_emails[1] if len(client_emails) >= 2 else ""

project_name_lower = project_name.lower()
client_match_found = False
for name in client_names:
    for part in name.lower().split():
        if len(part) >= 4 and part in project_name_lower:
            client_match_found = True
            break

# Warnings
print(f"PROJECT NUMBER:  {project_number}")
print(f"PROJECT NAME:    {project_name}")
print(f"ADDRESS:         {street_address}")
print(f"CITY:            {city}")
print(f"STATE:           {state}")
print(f"ZIP:             {zip_code}")
print(f"COUNTY:          {county}")
print(f"APN:             {apn}")
print(f"CLIENT 1:        {client_name_1}  {client_email_1}")
print(f"CLIENT 2:        {client_name_2}  {client_email_2}")

if not client_name_1:    print("WARNING: CLIENT NAME NOT DETECTED")
if not client_email_1:   print("WARNING: CLIENT EMAIL NOT DETECTED")
if not apn:              print("WARNING: APN NOT DETECTED")
if good_template and not zip_code: print("WARNING: ZIP CODE NOT DETECTED")
if not client_match_found: print("WARNING: CLIENT DOES NOT MATCH PROJECT NAME")
if apn_warning:          print("WARNING: APN FORMAT WAS CORRECTED")

# =========================
# STEP 7 — WRITE INFO FILE
# =========================

print("UI_STEP:Writing INFO file")
sys.stdout.flush()

new_filename = f"{project_number} INFO - {today_str()}.txt"
new_path     = os.path.join(ui_folder, new_filename)

info_lines_out = [
    f"PROJECT_NUMBER={project_number}\n",
    f"PROJECT_NAME={project_name}\n\n",
    f"TOT={existing_tot}\n\n",
    f"PROJECT_ADDRESS={street_address}\n",
    f"MANUAL_PROJECT_ADDRESS={manual_project_address}\n",
    f"CITY={city}\n",
    f"STATE={state}\n",
    f"ZIP_CODE={zip_code}\n\n",
    f"ASCE_RESOLVED_ADDRESS=\n",
    f"VERIFIED_PROJECT_ADDRESS=\n",
    f"VERIFIED_APN={existing_verified_apn}\n",
    f"VERIFIED_COUNTY=\n\n",
    f"COUNTY={county}\n",
    f"APN={apn}\n\n",
    f"CLIENT_NAME_1={client_name_1}\n",
    f"CLIENT_EMAIL_1={client_email_1}\n",
    f"CLIENT_NAME_2={client_name_2}\n",
    f"CLIENT_EMAIL_2={client_email_2}\n\n",
    f"PROJECT_DESCRIPTION={project_description}\n\n",
    f"CONTRACT_PDF={contract_pdf}\n",
    f"MONDAY_UPLOADED={existing_monday}\n",
    f"TOT_SNOW_LOAD=\n",
    f"ELEVATION=\n",
    f"TOT_SNOW_SCREENSHOT=\n",
    f"LOCATION_SCREENSHOT=\n",
    f"SEISMIC_SS=\n",
    f"SEISMIC_S1=\n",
    f"SEISMIC_FA=\n",
    f"SEISMIC_TL=\n",
    f"SEISMIC_SMS=\n",
    f"SEISMIC_SDS=\n",
    f"SEISMIC_RISK=\n",
    f"SEISMIC_CLASS=\n",
    f"SEISMIC_PDF_DONE=\n",
    f"ULT=\n",
]

# If overwriting, archive old file first
if info_path and os.path.exists(info_path):
    write_info_lines(info_path, project_root, info_lines_out)
    # write_info_lines handles archive and new file creation
else:
    # New file
    with open(new_path, "w", encoding="utf-8") as f:
        f.writelines(info_lines_out)

print("INFO FILE CREATED")
print(new_path)
print("DONE")