import sys
import pdfplumber
import xlwings as xw
import os
import re
import shutil

# =========================
# PROJECT NUMBER
# =========================

project_number = sys.argv[1]

# =========================
# YEAR PREFIX
# =========================

year_prefix = project_number[:2]

# =========================
# BASE FOLDER
# =========================

base_folder = (
    r"C:\Users\saxon\Dropbox\SHEAR FORCE"
    r"\1) CURRENT PROJECTS"
)

# =========================
# YEAR GROUP FOLDER
# =========================

year_group_folder = os.path.join(
    base_folder,
    f"{year_prefix}-XXX"
)

# =========================
# FIND PROJECT ROOT
# =========================

project_root = ""
project_folder_name = ""

for folder in os.listdir(year_group_folder):

    if folder.startswith(project_number):

        project_root = os.path.join(
            year_group_folder,
            folder
        )

        project_folder_name = folder

        break

if project_root == "":

    raise Exception(
        "PROJECT FOLDER NOT FOUND"
    )

# =========================
# PROJECT NAME
# =========================

project_name_only = (
    project_folder_name.replace(
        project_number,
        ""
    )
    .strip()
    .lstrip("-")
    .strip()
)

# =========================
# FOLDERS
# =========================

project_folder = os.path.join(
    project_root,
    "CALCULATIONS"
)

archive_folder = os.path.join(
    project_folder,
    "ARCHIVE"
)

# =========================
# FIND NEWEST INFO FILE
# =========================

archive_folder = os.path.join(
    project_root,
    "CALCULATIONS",
    "ARCHIVE"
)

info_path = ""

latest_time = 0

for file in os.listdir(archive_folder):

    upper_file = file.upper()

    if (
        file.endswith(".txt")
        and "INFO" in upper_file
        and project_number in upper_file
    ):

        full_path = os.path.join(
            archive_folder,
            file
        )

        modified_time = os.path.getmtime(
            full_path
        )

        if modified_time > latest_time:

            latest_time = modified_time

            info_path = full_path

if info_path == "":

    raise Exception(
        "INFO FILE NOT FOUND"
    )

print("\nINFO FILE FOUND")
print(info_path)

# =========================
# READ INFO FILE
# =========================

with open(
    info_path,
    "r",
    encoding="utf-8"
) as file:

    info_lines = file.readlines()

# =========================
# VARIABLES
# =========================

project_address = ""
city = ""
state = ""
zip_code = ""
county = ""
verified_apn = ""
tot_status = ""

# =========================
# EXTRACT INFO
# =========================

for line in info_lines:

    if line.startswith("PROJECT_ADDRESS="):

        project_address = (
            line.replace(
                "PROJECT_ADDRESS=",
                ""
            ).strip()
        )

    if line.startswith("CITY="):

        city = (
            line.replace(
                "CITY=",
                ""
            ).strip()
        )

    if line.startswith("STATE="):

        state = (
            line.replace(
                "STATE=",
                ""
            ).strip()
        )

    if line.startswith("ZIP_CODE="):

        zip_code = (
            line.replace(
                "ZIP_CODE=",
                ""
            ).strip()
        )

    if line.startswith("COUNTY="):

        county = (
            line.replace(
                "COUNTY=",
                ""
            ).strip()
        )

    if line.startswith("VERIFIED_APN="):

        verified_apn = (
            line.replace(
                "VERIFIED_APN=",
                ""
            ).strip()
        )

    if line.startswith("TOT="):

        tot_status = (
            line.replace(
                "TOT=",
                ""
            ).strip()
        )

# =========================
# STOP IF TOT
# =========================

if tot_status == "Y":

    print("\n====================")
    print("TOT PROJECT")
    print("====================")

    print(
        "\nUSE TOT_LAT.PY "
        "INSTEAD"
    )

    sys.exit()

# =========================
# FINAL ADDRESS VALUES
# =========================

street_address = project_address

city_state_zip = (
    f"{city}, {state} {zip_code}"
)

formatted_county_apn = ""

if (
    county != ""
    and verified_apn != ""
):

    formatted_county_apn = (
        f"{county} COUNTY APN: "
        f"{verified_apn}"
    )

# =========================
# FIND ASCE PDF
# =========================

pdf_path = ""

for file in os.listdir(project_folder):

    if (
        file.endswith(".pdf")
        and "ASCEDesignHazardsReport" in file
    ):

        pdf_path = os.path.join(
            project_folder,
            file
        )

        break

if pdf_path == "":

    raise Exception(
        "NO ASCE PDF FOUND"
    )

# =========================
# LAT TEMPLATE
# =========================

template_folder = (
    r"C:\Users\saxon\Dropbox\SHEAR FORCE\4) TEMPLATES\CALC EXCEL TEMPLATES"
)

template_path = os.path.join(
    template_folder,
    "SF Lateral Design Template 3.28.26.xlsm"
)

if os.path.exists(template_path) == False:

    raise Exception(
        "LAT TEMPLATE NOT FOUND"
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
# OUTPUT FILE NAME
# =========================

final_excel_name = (
    f"{project_number} "
    f"{project_name_only}"
    f" - LAT XL - "
    f"{formatted_date}.xlsm"
)

final_excel_path = os.path.join(
    project_folder,
    final_excel_name
)

# =========================
# HANDLE EXISTING FILES
# =========================

base_name = os.path.splitext(
    final_excel_name
)[0]

extension = ".xlsm"

counter = 2

new_final_excel_path = (
    final_excel_path
)

while os.path.exists(
    new_final_excel_path
):

    new_final_excel_path = os.path.join(
        project_folder,
        f"{base_name} "
        f"({counter})"
        f"{extension}"
    )

    counter += 1

# =========================
# COPY TEMPLATE
# =========================

shutil.copy(
    template_path,
    new_final_excel_path
)

print("\nNEW LAT FILE CREATED:")

print(new_final_excel_path)

excel_path = (
    new_final_excel_path
)

# =========================
# OPEN LAT FILE
# =========================

app = xw.App(
    visible=False
)

app.display_alerts = False

wb = app.books.open(
    os.path.abspath(excel_path)
)

cover_ws = wb.sheets[0]

# =========================
# OPEN ASCE PDF
# =========================

with pdfplumber.open(pdf_path) as pdf:

    page = pdf.pages[2]

    text = page.extract_text()

    lines = text.split("\n")

# =========================
# VARIABLES
# =========================

ss_value = ""
sms_value = ""
sds_value = ""
s1_value = ""
sm1_value = ""
sd1_value = ""
seismic_category = ""
wind_speed = ""
special_wind_region = False

# =========================
# EXTRACT VALUES
# =========================

for i, line in enumerate(lines):

    if "MS S" in line:

        previous_line = lines[i - 1]

        parts = previous_line.split()

        sms_value = parts[2]
        ss_value = parts[-1]

    if "M1 1" in line:

        previous_line = lines[i - 1]

        parts = previous_line.split()

        sm1_value = parts[2]
        s1_value = parts[-1]

    if "DS S30" in line:

        previous_line = lines[i - 1]

        parts = previous_line.split()

        sds_value = parts[2]

    if "D1" in line:

        previous_line = lines[i - 1]

        parts = previous_line.split()

        sd1_value = parts[-1]

    if "Seismic Design Category" in line:

        seismic_category = (
            line.split(":")[-1]
            .strip()
        )

# =========================
# WIND PAGE
# =========================

with pdfplumber.open(pdf_path) as pdf:

    wind_page = pdf.pages[1]

    wind_text = (
        wind_page.extract_text()
    )

wind_lines = wind_text.split("\n")

for line in wind_lines:

    if "Special Wind Region" in line:

        special_wind_region = True

# =========================
# WIND SPEED
# =========================

with pdfplumber.open(pdf_path) as pdf:

    first_page = pdf.pages[0]

    first_page_text = (
        first_page.extract_text()
    )

first_page_lines = (
    first_page_text.split("\n")
)

for line in first_page_lines:

    if "Wind Speed" in line:

        wind_match = re.search(
            r"\d+",
            line
        )

        if wind_match:

            wind_speed = (
                wind_match.group()
            )

# =========================
# RESULTS
# =========================

print("\nRESULTS:")

print("Ss =", ss_value)
print("Sms =", sms_value)
print("Sds =", sds_value)
print("S1 =", s1_value)
print("Sm1 =", sm1_value)
print("Sd1 =", sd1_value)

print(
    "Seismic Category =",
    seismic_category
)

print(
    "Special Wind Region =",
    special_wind_region
)

print(
    "Wind Speed =",
    wind_speed
)

# =========================
# WRITE TO EXCEL
# =========================

calc_ws = wb.sheets[1]

# COVER PAGE

cover_ws.range("D35").value = (
    project_number
)

cover_ws.range("A10").value = (
    project_name_only
)

cover_ws.range("A11").value = (
    street_address
)

cover_ws.range("A12").value = (
    city_state_zip
)

cover_ws.range("A13").value = (
    formatted_county_apn
)

# SEISMIC

calc_ws.range("F4").value = (
    seismic_category
)

calc_ws.range("F6").value = (
    ss_value
)

calc_ws.range("F7").value = (
    sms_value
)

calc_ws.range("F8").value = (
    sds_value
)

calc_ws.range("F9").value = (
    s1_value
)

calc_ws.range("F10").value = (
    sm1_value
)

calc_ws.range("F11").value = (
    sd1_value
)

# WIND

if special_wind_region == False:

    calc_ws.range("J8").value = (
        wind_speed
    )

    print(
        "\nSTANDARD WIND SPEED USED"
    )

else:

    print(
        "\nSPECIAL WIND REGION DETECTED"
    )

    print(
        "J8 NOT UPDATED"
    )

# =========================
# OPEN TO FIRST SHEET
# =========================

cover_ws.activate()

wb.app.api.ActiveWindow.ScrollRow = 1
wb.app.api.ActiveWindow.ScrollColumn = 1

# =========================
# SAVE
# =========================

wb.save()

print("\nLAT COMPLETE")

print(excel_path)

# =========================
# CLOSE
# =========================

wb.close()
app.quit()

print("\n\n\nDONE\n\n\n")