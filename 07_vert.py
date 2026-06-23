import sys
import os
import shutil
import re
from datetime import datetime

import pdfplumber
import xlwings as xw

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

calculations_folder = os.path.join(
    project_root,
    "CALCULATIONS"
)

archive_folder = os.path.join(
    calculations_folder,
    "ARCHIVE"
)

# =========================
# FIND NEWEST INFO FILE
# =========================

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

project_description = ""

# =========================
# EXTRACT INFO
# =========================

for line in info_lines:

    if line.startswith("PROJECT_DESCRIPTION="):

        project_description = (
            line.replace(
                "PROJECT_DESCRIPTION=",
                ""
            ).strip()
        )

# =========================
# TEMPLATE PATH
# =========================

template_folder = (
    r"C:\Users\saxon\Dropbox\SHEAR FORCE"
    r"\4) TEMPLATES"
    r"\CALC EXCEL TEMPLATES"
)

template_path = ""

for file in os.listdir(template_folder):

    if (
        file.endswith(".xlsm")
        and "SF Vertical Package Template"
        in file
    ):

        template_path = os.path.join(
            template_folder,
            file
        )

        break

if template_path == "":

    raise Exception(
        "VERT TEMPLATE NOT FOUND"
    )

print("\nVERT TEMPLATE FOUND")
print(template_path)

# =========================
# DATE STRING
# =========================

today = datetime.now()

formatted_date = (
    f"{today.month}."
    f"{today.day}."
    f"{str(today.year)[2:]}"
)

# =========================
# NEW VERT FILE NAME
# =========================

base_vert_filename = (
    f"{project_number} "
    f"{project_name_only}"
    f" - VERT XL - "
    f"{formatted_date}"
)

vert_filename = (
    f"{base_vert_filename}.xlsm"
)

vert_path = os.path.join(
    calculations_folder,
    vert_filename
)

# =========================
# RENAME IF FILE EXISTS
# =========================

counter = 2

while os.path.exists(vert_path):

    vert_filename = (
        f"{base_vert_filename}"
        f" ({counter}).xlsm"
    )

    vert_path = os.path.join(
        calculations_folder,
        vert_filename
    )

    counter += 1

# =========================
# COPY TEMPLATE
# =========================

shutil.copy2(
    template_path,
    vert_path
)

print("\nVERT TEMPLATE COPIED")
print(vert_path)

# =========================
# FIND LAT FILE
# =========================

lat_path = ""

lat_files = []

for file in os.listdir(calculations_folder):

    upper_file = file.upper()

    if (
        file.endswith(".xlsm")
        and "LAT XL" in upper_file
        and "VERT" not in upper_file
    ):

        lat_files.append(file)

if len(lat_files) == 0:

    raise Exception(
        "LAT WORKBOOK NOT FOUND"
    )

# =========================
# MOST RECENT LAT
# =========================

latest_time = 0

for file in lat_files:

    full_path = os.path.join(
        calculations_folder,
        file
    )

    modified_time = os.path.getmtime(
        full_path
    )

    if modified_time > latest_time:

        latest_time = modified_time

        lat_path = full_path

print("\nLAT FILE FOUND")
print(lat_path)

# =========================
# FIND ASCE PDF
# =========================

asce_pdf = ""

pdf_files = []

for file in os.listdir(calculations_folder):

    if (
        file.endswith(".pdf")
        and "ASCEDesignHazardsReport"
        in file
    ):

        pdf_files.append(file)

if len(pdf_files) == 0:

    raise Exception(
        "ASCE PDF NOT FOUND"
    )

# =========================
# MOST RECENT PDF
# =========================

latest_time = 0

for file in pdf_files:

    full_path = os.path.join(
        calculations_folder,
        file
    )

    modified_time = os.path.getmtime(
        full_path
    )

    if modified_time > latest_time:

        latest_time = modified_time

        asce_pdf = full_path

print("\nASCE PDF FOUND")
print(asce_pdf)

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
# VALIDATE DESCRIPTION
# =========================

word_count = len(
    project_description.split()
)

print("\nDESCRIPTION WORD COUNT:")
print(word_count)

good_description = (
    word_count >= 10
)

if good_description:

    print(
        "\nGOOD DESCRIPTION FOUND"
    )

else:

    print(
        "\nBAD DESCRIPTION"
    )

    print(
        "\nSKIPPING TEXTBOX UPDATE"
    )

# =========================
# EXTRACT SNOW LOAD
# =========================

snow_load = ""

with pdfplumber.open(asce_pdf) as pdf:

    page_5 = pdf.pages[4]

    page_text = (
        page_5.extract_text()
    )

snow_match = re.search(
    r"Ground snow load.*?(\d+)\s*lb",
    page_text,
    re.IGNORECASE | re.DOTALL
)

if snow_match:

    snow_load = (
        snow_match.group(1)
    )

print("\nSNOW LOAD:")
print(snow_load)

# =========================
# OPEN EXCEL
# =========================

app = xw.App(
    visible=False
)

app.display_alerts = False

try:

    lat_wb = app.books.open(
        os.path.abspath(lat_path)
    )

    vert_wb = app.books.open(
        os.path.abspath(vert_path)
    )

    # =========================
    # SHEETS
    # =========================

    lat_sheet_1 = lat_wb.sheets[0]

    vert_sheet_1 = vert_wb.sheets[0]
    vert_sheet_2 = vert_wb.sheets[1]
    vert_sheet_3 = vert_wb.sheets[2]

    # =========================
    # COPY COVER INFO
    # =========================

    vert_sheet_1.range("A10").value = (
        lat_sheet_1.range("A10").value
    )

    vert_sheet_1.range("A11").value = (
        lat_sheet_1.range("A11").value
    )

    vert_sheet_1.range("A12").value = (
        lat_sheet_1.range("A12").value
    )

    vert_sheet_1.range("A13").value = (
        lat_sheet_1.range("A13").value
    )

    vert_sheet_1.range("D37").value = (
        lat_sheet_1.range("D35").value
    )

    print("\nLAT COVER DATA COPIED")

    # =========================
    # UPDATE TEXTBOX
    # =========================

    textbox_updated = False

    for shape in vert_sheet_2.api.Shapes:

        try:

            shape_text = (
                shape.TextFrame.Characters().Text
            )

            if (
                good_description
                and (
                    "PROJECT DESCRIPTION"
                    in shape_text.upper()
                    or len(shape_text.strip()) > 20
                )
            ):

                shape.TextFrame.Characters().Text = (
                    project_description
                )

                textbox_updated = True

                print(
                    "\nTEXTBOX UPDATED"
                )

                break

        except:

            pass

    if (
        good_description
        and textbox_updated == False
    ):

        raise Exception(
            "TEXTBOX NOT FOUND"
        )

    # =========================
    # SNOW LOAD
    # =========================

    if snow_load != "":

        vert_sheet_3.range("F17").value = (
            snow_load
        )

        print("\nSNOW LOAD WRITTEN")

    # =========================
    # OPEN TO FIRST SHEET
    # =========================

    vert_sheet_1.activate()

    vert_wb.app.api.ActiveWindow.ScrollRow = 1
    vert_wb.app.api.ActiveWindow.ScrollColumn = 1

    # =========================
    # SAVE
    # =========================

    vert_wb.save()

    print("\nVERT COMPLETE")
    print(vert_path)

finally:

    try:
        lat_wb.close()
    except:
        pass

    try:
        vert_wb.close()
    except:
        pass

    app.quit()

print("\n\n\nDONE\n\n\n")