import pdfplumber
import os
import re
import time
import ctypes
import sys

# =========================
# BASE FOLDER
# =========================

base_folder = (
    r"C:\Users\saxon\Dropbox\SHEAR FORCE"
    r"\1) CURRENT PROJECTS"
)

# =========================
# PROJECT NUMBER
# =========================

project_number = sys.argv[1]

# =========================
# YEAR PREFIX
# =========================

year_prefix = project_number[:2]

# =========================
# YEAR FOLDER
# =========================

year_folder = os.path.join(
    base_folder,
    f"{year_prefix}-XXX"
)

# =========================
# FIND PROJECT
# =========================

project_root = ""
project_folder_name = ""

for folder in os.listdir(year_folder):

    if folder.startswith(project_number):

        project_root = os.path.join(
            year_folder,
            folder
        )

        project_folder_name = folder

        break

if project_root == "":

    raise Exception(
        "PROJECT NOT FOUND"
    )

# =========================
# PROJECT NAME
# =========================

project_name = (
    project_folder_name
    .replace(project_number, "")
    .strip()
    .lstrip("-")
    .strip()
)

# =========================
# FOLDERS
# =========================

contract_folder = os.path.join(
    project_root,
    "CONTRACT"
)

calculations_folder = os.path.join(
    project_root,
    "CALCULATIONS"
)

archive_folder = os.path.join(
    calculations_folder,
    "ARCHIVE"
)

os.makedirs(
    archive_folder,
    exist_ok=True
)

# =========================
# DATE STRING
# =========================

from datetime import datetime

today = datetime.now()

formatted_date = (
    f"{today.month}."
    f"{today.day}."
    f"{str(today.year)[2:]}"
)

# =========================
# INFO FILE
# =========================

info_filename = (
    f"{project_number} "
    f"INFO - "
    f"{formatted_date}.txt"
)

info_path = os.path.join(
    archive_folder,
    info_filename
)

# =========================
# FIND CONTRACT PDF
# =========================

contract_pdf = ""

for file in os.listdir(contract_folder):

    if file.lower().endswith(".pdf"):

        contract_pdf = os.path.join(
            contract_folder,
            file
        )

        break

if contract_pdf == "":

    raise Exception(
        "NO CONTRACT PDF FOUND"
    )

print("\nCONTRACT PDF FOUND")
print(contract_pdf)

# =========================
# READ PDF
# =========================

with pdfplumber.open(contract_pdf) as pdf:

    text = ""

    for page in pdf.pages:

        extracted = page.extract_text()

        if extracted:

            text += extracted + "\n"

# =========================
# PROJECT DESCRIPTION
# =========================

project_description = ""

if (
    "Project Description" in text
    and "Scope" in text
):

    description_lines = []

    capture = False

    description_text_lines = (
        text.split("\n")
    )

    for line in description_text_lines:

        clean_line = line.strip()

        if "Project Description" in clean_line:

            capture = True

            continue

        if (
            capture
            and "Scope" in clean_line
        ):

            break

        if capture:

            if clean_line != "":

                description_lines.append(
                    clean_line
                )

    project_description = " ".join(
        description_lines
    )

# =========================
# CLEAN DESCRIPTION
# =========================

project_description = re.sub(
    r"\s+",
    " ",
    project_description
).strip()

print("\nPROJECT DESCRIPTION:")
print(project_description)

# =========================
# CLEAN TEXT
# =========================

text = re.sub(
    r"\(cid:\d+\)",
    "",
    text
)

lines = text.split("\n")

lower_lines = [
    line.lower().strip()
    for line in lines
]

# =========================
# VARIABLES
# =========================

street_address = ""
city = ""
state = ""
zip_code = ""

county = ""
apn = ""

client_names = []
client_emails = []

client_name_1 = ""
client_name_2 = ""

client_email_1 = ""
client_email_2 = ""

good_template = False

manual_project_address = ""

# =========================
# GOOD TEMPLATE ADDRESS
# =========================

try:

    for i, line in enumerate(lower_lines):

        if "re:" in line:

            print(
                "\nFOUND RE LINE:"
            )

            print(lines[i])

            for j in range(
                i,
                min(i + 10, len(lines))
            ):

                possible_address = (
                    lines[j].strip()
                )

                has_number = any(
                    char.isdigit()
                    for char in possible_address
                )

                has_comma = (
                    "," in possible_address
                )

                if (
                    has_number
                    and has_comma
                ):

                    address_parts = [
                        part.strip()
                        for part in possible_address.split(",")
                    ]

                    if len(address_parts) >= 3:

                        street_address = (
                            address_parts[0]
                        )

                        city = (
                            address_parts[1]
                        )

                        state_zip = (
                            address_parts[2]
                        )

                        state_match = re.search(
                            r"\b[A-Z]{2}\b",
                            state_zip
                        )

                        zip_match = re.search(
                            r"\b\d{5}\b",
                            state_zip
                        )

                        if state_match:

                            state = (
                                state_match.group(0)
                            )

                        if zip_match:

                            zip_code = (
                                zip_match.group(0)
                            )

                        good_template = True

                        print(
                            "\nGOOD TEMPLATE ADDRESS FOUND"
                        )

                        break

            if good_template:

                break

except Exception as e:

    print(
        "\nGOOD TEMPLATE EXTRACTION FAILED"
    )

    print(e)

# =========================
# BAD TEMPLATE
# =========================

if good_template == False:

    print(
        "\nBAD TEMPLATE DETECTED"
    )

    os.system(
        f'start "" "{contract_pdf}"'
    )

    time.sleep(1)

    ctypes.windll.user32.SetForegroundWindow(
        ctypes.windll.kernel32.GetConsoleWindow()
    )

    print(
        "\nCONTRACT PDF OPENED"
    )

    manual_address = input(
        "\nType project address manually: "
    ).strip()

    if manual_address == "":

        raise Exception(
            "NO MANUAL ADDRESS ENTERED"
        )

    street_address = manual_address

    manual_project_address = (
        manual_address
    )

# =========================
# APN EXTRACTION
# =========================

apn_warning = False

for line in lines:

    lower_line = line.lower()

    if "county apn" in lower_line:

        # =========================
        # COUNTY
        # =========================

        if "placer" in lower_line:

            county = "PLACER"

        elif "nevada" in lower_line:

            county = "NEVADA"

        # =========================
        # FIND RAW APN
        # =========================

        raw_apn_match = re.search(
            r"(\d[\d\-]{6,20}\d)",
            line
        )

        if raw_apn_match:

            raw_apn = (
                raw_apn_match.group(1)
            )

            print("\nRAW APN FOUND:")
            print(raw_apn)

            # =========================
            # DIGITS ONLY
            # =========================

            apn_digits = re.sub(
                r"\D",
                "",
                raw_apn
            )

            print("\nAPN DIGITS:")
            print(apn_digits)

            # =========================
            # FIX COMMON BAD FORMAT
            # =========================

            if len(apn_digits) >= 9:

                core_digits = (
                    apn_digits[:9]
                )

                apn = (
                    f"{core_digits[0:3]}-"
                    f"{core_digits[3:6]}-"
                    f"{core_digits[6:9]}"
                )

                print("\nFORMATTED APN:")
                print(apn)

                # =========================
                # WARNING
                # =========================

                if raw_apn != apn:

                    apn_warning = True

            else:

                print(
                    "\nWARNING: "
                    "NOT ENOUGH DIGITS "
                    "FOR APN"
                )

        break

# =========================
# CLIENT EMAILS
# =========================

client_emails = re.findall(
    r'[\w\.-]+@[\w\.-]+\.\w+',
    text
)

client_emails = list(
    dict.fromkeys(client_emails)
)

# =========================
# CLIENT NAMES
# =========================

for i, line in enumerate(lines):

    lower_line = line.lower().strip()

    if (
        "via e-mail:" in lower_line
        or "via email:" in lower_line
    ):

        for j in range(i - 1, -1, -1):

            possible_name = (
                lines[j].strip()
            )

            if possible_name == "":

                continue

            if (
                "@" in possible_name
                or "proposal" in possible_name.lower()
                or "engineering" in possible_name.lower()
            ):

                continue

            split_names = re.split(
                r",|\+| and ",
                possible_name
            )

            for split_name in split_names:

                clean_name = (
                    split_name.strip()
                )

                word_count = len(
                    clean_name.split()
                )

                if (
                    word_count >= 2
                    and word_count <= 5
                ):

                    has_letter = any(
                        char.isalpha()
                        for char in clean_name
                    )

                    if has_letter:

                        client_names.append(
                            clean_name.upper()
                        )

            break

# =========================
# REMOVE DUPLICATES
# =========================

client_names = list(
    dict.fromkeys(client_names)
)

# =========================
# FORMAT CLIENT VALUES
# =========================

if len(client_names) >= 1:

    client_name_1 = (
        client_names[0]
    )

if len(client_names) >= 2:

    client_name_2 = (
        client_names[1]
    )

if len(client_emails) >= 1:

    client_email_1 = (
        client_emails[0]
    )

if len(client_emails) >= 2:

    client_email_2 = (
        client_emails[1]
    )

# =========================
# CLIENT MATCH WARNING
# =========================

project_name_lower = (
    project_name.lower()
)

client_match_found = False

for name in client_names:

    name_parts = (
        name.lower().split()
    )

    for part in name_parts:

        if len(part) >= 4:

            if part in project_name_lower:

                client_match_found = True

                break

# =========================
# PRINT RESULTS
# =========================

print("\n====================")
print("EXTRACTED INFO")
print("====================")

print("\nPROJECT NUMBER:")
print(project_number)

print("\nPROJECT NAME:")
print(project_name)

print("\nPROJECT ADDRESS:")
print(street_address)

print("\nCITY:")
print(city)

print("\nSTATE:")
print(state)

print("\nZIP CODE:")
print(zip_code)

print("\nCOUNTY:")
print(county)

print("\nAPN:")
print(apn)

print("\nCLIENT NAME 1:")
print(client_name_1)

print("\nCLIENT EMAIL 1:")
print(client_email_1)

print("\nCLIENT NAME 2:")
print(client_name_2)

print("\nCLIENT EMAIL 2:")
print(client_email_2)

print("\nPROJECT DESCRIPTION:")
print(project_description)

# =========================
# WARNINGS
# =========================

if client_name_1 == "":

    print(
        "\nWARNING: CLIENT NAME NOT DETECTED"
    )

if client_email_1 == "":

    print(
        "\nWARNING: CLIENT EMAIL NOT DETECTED"
    )

if apn == "":

    print(
        "\nWARNING: APN NOT DETECTED"
    )

if good_template and zip_code == "":

    print(
        "\nWARNING: ZIP CODE NOT DETECTED"
    )

if client_match_found == False:

    print(
        "\nWARNING: CLIENT DOES NOT MATCH PROJECT NAME"
    )

if apn_warning:

    print(
        "\nWARNING: APN FORMAT "
        "WAS CORRECTED"
    )
# =========================
# WRITE INFO FILE
# =========================

with open(
    info_path,
    "w",
    encoding="utf-8"
) as file:

    file.write(
        f"PROJECT_NUMBER={project_number}\n"
    )

    file.write(
        f"PROJECT_NAME={project_name}\n\n"
    )

    file.write(
        f"TOT=\n\n"
    )

    file.write(
        f"PROJECT_ADDRESS="
        f"{street_address}\n"
    )

    file.write(
        f"MANUAL_PROJECT_ADDRESS="
        f"{manual_project_address}\n"
    )

    file.write(
        f"CITY={city}\n"
    )

    file.write(
        f"STATE={state}\n"
    )

    file.write(
        f"ZIP_CODE={zip_code}\n\n"
    )

    file.write(
        f"ASCE_RESOLVED_ADDRESS=\n"
    )

    file.write(
        f"VERIFIED_PROJECT_ADDRESS=\n"
    )

    file.write(
        f"VERIFIED_APN=\n"
    )

    file.write(
        f"VERIFIED_COUNTY=\n\n"
    )

    file.write(
        f"COUNTY={county}\n"
    )

    file.write(
        f"APN={apn}\n\n"
    )

    file.write(
        f"CLIENT_NAME_1="
        f"{client_name_1}\n"
    )

    file.write(
        f"CLIENT_EMAIL_1="
        f"{client_email_1}\n"
    )

    file.write(
        f"CLIENT_NAME_2="
        f"{client_name_2}\n"
    )

    file.write(
        f"CLIENT_EMAIL_2="
        f"{client_email_2}\n\n"
    )

    file.write(
        f"PROJECT_DESCRIPTION="
        f"{project_description}\n\n"
    )

    file.write(
        f"CONTRACT_PDF="
        f"{contract_pdf}\n"
    )

print("\n====================")
print("INFO FILE CREATED")
print("====================")

print(info_path)

print("\n\nDONE\n\n")