import pdfplumber
import os
import re
import sys
import threading
from datetime import datetime

# =========================
# BASE FOLDER
# =========================

base_folder = (
    r"C:\Users\saxon\Dropbox\SHEAR FORCE"
    r"\1) CURRENT PROJECTS"
)

project_number = sys.argv[1]
year_prefix    = project_number[:2]

year_folder = os.path.join(
    base_folder, f"{year_prefix}-XXX"
)

# =========================
# FIND PROJECT
# =========================

project_root        = ""
project_folder_name = ""

for folder in os.listdir(year_folder):
    if folder.startswith(project_number):
        project_root        = os.path.join(year_folder, folder)
        project_folder_name = folder
        break

if project_root == "":
    raise Exception("PROJECT NOT FOUND")

project_name = (
    project_folder_name
    .replace(project_number, "")
    .strip().lstrip("-").strip()
)

# =========================
# FOLDERS
# =========================

contract_folder     = os.path.join(project_root, "CONTRACT")
calculations_folder = os.path.join(project_root, "CALCULATIONS")
archive_folder      = os.path.join(calculations_folder, "ARCHIVE")

os.makedirs(archive_folder, exist_ok=True)

# =========================
# STEP 1 — CHECK FOR EXISTING INFO FILES
# This is the very first thing — instant
# =========================

print("UI_STEP:Checking for existing INFO files")
sys.stdout.flush()

existing_infos = []
print(f"SEARCHING ARCHIVE: {archive_folder}")
sys.stdout.flush()
for file in os.listdir(archive_folder):
    upper = file.upper()
    print(f"FOUND FILE: {file}")
    sys.stdout.flush()
    if (
        file.endswith(".txt")
        and "INFO" in upper
        and project_number in upper
    ):
        existing_infos.append(
            os.path.join(archive_folder, file)
        )

print(f"MATCHING INFO FILES: {len(existing_infos)}")
sys.stdout.flush()
existing_infos.sort(key=os.path.getmtime, reverse=True)

info_path     = ""
existing_tot  = ""
existing_verified_apn = ""
existing_monday = ""

if len(existing_infos) > 0:
    files_str = "|".join(existing_infos)
    print(f"UI_INFO_EXISTS:{files_str}")
    sys.stdout.flush()
    response = sys.stdin.readline().strip()

    if response == "SKIP":
        print("INFO FILE ALREADY EXISTS — SKIPPING")
        print("DONE")
        sys.exit()

    elif response == "OVERWRITE":
        print("OVERWRITING OLDEST INFO FILE")
        info_path = existing_infos[-1]

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

if contract_pdf == "":
    raise Exception("NO CONTRACT PDF FOUND")

print("CONTRACT PDF FOUND")
sys.stdout.flush()

# =========================
# BUILD NEW INFO PATH IF NEEDED
# =========================

if not info_path:
    today          = datetime.now()
    formatted_date = (
        f"{today.month}.{today.day}.{str(today.year)[2:]}"
    )
    base_name = f"{project_number} INFO - {formatted_date}"
    extension = ".txt"
    info_path = os.path.join(
        archive_folder, f"{base_name}{extension}"
    )
    counter = 2
    while os.path.exists(info_path):
        info_path = os.path.join(
            archive_folder,
            f"{base_name} ({counter}){extension}"
        )
        counter += 1

# =========================
# STEP 3 — START READING PDF IN BACKGROUND
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

pdf_thread = threading.Thread(target=read_pdf, daemon=True)
pdf_thread.start()

print("UI_STEP:Reading PDF")
sys.stdout.flush()

# =========================
# STEP 4 — PDF OPEN DIALOG
# Shows while PDF reads in background
# =========================

print(f"UI_OPEN_PDF:{contract_pdf}")
sys.stdout.flush()

# =========================
# WAIT FOR PDF READ TO FINISH
# =========================

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
        if capture and clean_line != "":
            description_lines.append(clean_line)
    project_description = " ".join(description_lines)

project_description = re.sub(
    r"\s+", " ", project_description
).strip()

# =========================
# CLEAN TEXT
# =========================

text        = re.sub(r"\(cid:\d+\)", "", text)
lines       = text.split("\n")
lower_lines = [line.lower().strip() for line in lines]

# =========================
# STEP 5 — EXTRACT ADDRESS
# =========================

print("UI_STEP:Extracting address")
sys.stdout.flush()

street_address         = ""
city                   = ""
state                  = ""
zip_code               = ""
county                 = ""
apn                    = ""
client_names           = []
client_emails          = []
good_template          = False
manual_project_address = ""
apn_warning            = False
client_match_found     = True

try:
    for i, line in enumerate(lower_lines):
        if "re:" in line:
            for j in range(i, min(i + 10, len(lines))):
                possible_address = lines[j].strip()
                has_number = any(
                    char.isdigit() for char in possible_address
                )
                has_comma = "," in possible_address
                if has_number and has_comma:
                    address_parts = [
                        p.strip()
                        for p in possible_address.split(",")
                    ]
                    if len(address_parts) >= 3:
                        street_address = address_parts[0]
                        city           = address_parts[1]
                        state_zip      = address_parts[2]
                        state_match = re.search(
                            r"\b[A-Z]{2}\b", state_zip
                        )
                        zip_match = re.search(
                            r"\b\d{5}\b", state_zip
                        )
                        if state_match:
                            state = state_match.group(0)
                        if zip_match:
                            zip_code = zip_match.group(0)
                        good_template = True
                        break
            if good_template:
                break
except Exception as e:
    print(f"GOOD TEMPLATE EXTRACTION FAILED: {e}")

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
# STEP 6 — EXTRACT APN
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
        raw_apn_match = re.search(
            r"(\d[\d\-]{6,20}\d)", line
        )
        if raw_apn_match:
            raw_apn    = raw_apn_match.group(1)
            apn_digits = re.sub(r"\D", "", raw_apn)
            if len(apn_digits) >= 9:
                core_digits = apn_digits[:9]
                apn = (
                    f"{core_digits[0:3]}-"
                    f"{core_digits[3:6]}-"
                    f"{core_digits[6:9]}"
                )
                if raw_apn != apn:
                    apn_warning = True
            else:
                print("WARNING: NOT ENOUGH DIGITS FOR APN")
        break

# =========================
# STEP 7 — EXTRACT CLIENT INFO
# =========================

print("UI_STEP:Extracting client info")
sys.stdout.flush()

client_emails = re.findall(
    r'[\w\.-]+@[\w\.-]+\.\w+', text
)
client_emails = list(dict.fromkeys(client_emails))

for i, line in enumerate(lines):
    lower_line = line.lower().strip()
    if (
        "via e-mail:" in lower_line
        or "via email:" in lower_line
    ):
        for j in range(i - 1, -1, -1):
            possible_name = lines[j].strip()
            if not possible_name:
                continue
            if (
                "@" in possible_name
                or "proposal" in possible_name.lower()
                or "engineering" in possible_name.lower()
            ):
                continue
            split_names = re.split(
                r",|\+| and ", possible_name
            )
            for split_name in split_names:
                clean_name = split_name.strip()
                word_count = len(clean_name.split())
                if word_count >= 2 and word_count <= 5:
                    if any(
                        char.isalpha()
                        for char in clean_name
                    ):
                        client_names.append(
                            clean_name.upper()
                        )
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

# =========================
# PRINT RESULTS
# =========================

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

if not client_name_1:
    print("WARNING: CLIENT NAME NOT DETECTED")
if not client_email_1:
    print("WARNING: CLIENT EMAIL NOT DETECTED")
if not apn:
    print("WARNING: APN NOT DETECTED")
if good_template and not zip_code:
    print("WARNING: ZIP CODE NOT DETECTED")
if not client_match_found:
    print("WARNING: CLIENT DOES NOT MATCH PROJECT NAME")
if apn_warning:
    print("WARNING: APN FORMAT WAS CORRECTED")

# =========================
# STEP 8 — WRITE INFO FILE
# =========================

print("UI_STEP:Writing INFO file")
sys.stdout.flush()

with open(info_path, "w", encoding="utf-8") as file:
    file.write(f"PROJECT_NUMBER={project_number}\n")
    file.write(f"PROJECT_NAME={project_name}\n\n")
    file.write(f"TOT={existing_tot}\n\n")
    file.write(f"PROJECT_ADDRESS={street_address}\n")
    file.write(
        f"MANUAL_PROJECT_ADDRESS={manual_project_address}\n"
    )
    file.write(f"CITY={city}\n")
    file.write(f"STATE={state}\n")
    file.write(f"ZIP_CODE={zip_code}\n\n")
    file.write(f"ASCE_RESOLVED_ADDRESS=\n")
    file.write(f"VERIFIED_PROJECT_ADDRESS=\n")
    file.write(f"VERIFIED_APN={existing_verified_apn}\n")
    file.write(f"VERIFIED_COUNTY=\n\n")
    file.write(f"COUNTY={county}\n")
    file.write(f"APN={apn}\n\n")
    file.write(f"CLIENT_NAME_1={client_name_1}\n")
    file.write(f"CLIENT_EMAIL_1={client_email_1}\n")
    file.write(f"CLIENT_NAME_2={client_name_2}\n")
    file.write(f"CLIENT_EMAIL_2={client_email_2}\n\n")
    file.write(
        f"PROJECT_DESCRIPTION={project_description}\n\n"
    )
    file.write(f"CONTRACT_PDF={contract_pdf}\n")
    file.write(f"MONDAY_UPLOADED={existing_monday}\n")

print("INFO FILE CREATED")
print(info_path)
print("DONE")