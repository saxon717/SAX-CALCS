from playwright.sync_api import sync_playwright
from difflib import SequenceMatcher

import os
import re
import sys
from datetime import datetime

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

project_name = ""
project_address = ""

city = ""
state = ""
zip_code = ""

tot_status = ""

# =========================
# EXTRACT INFO
# =========================

for line in info_lines:

    if line.startswith("PROJECT_NAME="):

        project_name = (
            line.replace(
                "PROJECT_NAME=",
                ""
            ).strip()
        )

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
        "\nUSE TOT_ASCE.PY "
        "INSTEAD"
    )

    sys.exit()

# =========================
# CALCULATIONS FOLDER
# =========================

calculations_folder = os.path.join(
    project_root,
    "CALCULATIONS"
)

# =========================
# TODAY DATE
# =========================

today_date = datetime.today().strftime(
    "%m.%d.%y"
)

today_date = today_date.lstrip(
    "0"
).replace(
    ".0",
    "."
)

# =========================
# FINAL PDF NAME
# =========================

final_pdf_name = (
    f"{project_number} "
    f"{project_name}"
    f" - ASCEDesignHazardsReport"
    f" - {today_date}.pdf"
)

final_pdf_path = os.path.join(
    calculations_folder,
    final_pdf_name
)

# =========================
# CLEAN ADDRESS FUNCTION
# =========================

def clean_address(text):

    text = text.lower()

    replacements = {
        "street": "st",
        "avenue": "ave",
        "road": "rd",
        "drive": "dr",
        "lane": "ln",
        "court": "ct",
        "boulevard": "blvd",
        "place": "pl",
        "california": "ca",
        "nevada": "nv"
    }

    for old, new in replacements.items():

        text = text.replace(
            old,
            new
        )

    text = re.sub(
        r"[^a-z0-9 ]",
        "",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    return text

# =========================
# PLAYWRIGHT
# =========================

with sync_playwright() as p:

    browser = p.chromium.launch(
        headless=False
    )

    context = browser.new_context(
        accept_downloads=True
    )

    page = context.new_page()

    # =========================
    # OPEN WEBSITE
    # =========================

    page.goto(
        "https://ascehazardtool.org/",
        timeout=120000
    )

    print("\nWEBSITE OPENED")

    # =========================
    # WAIT
    # =========================

    page.wait_for_timeout(3000)

    # =========================
    # CLOSE ASCE POPUP
    # =========================

    try:

        page.locator(
            "#welcomePopup > div.popup-header.blue.darken-3.welcome-header > span.details-popup-close-icon"
        ).click(force=True)

        print(
            "\nASCE POPUP CLOSED"
        )

    except:

        print(
            "\nASCE POPUP NOT FOUND"
        )

    # =========================
    # CLOSE COOKIE POPUP
    # =========================

    page.wait_for_timeout(1000)

    try:

        page.locator(
            "button:has-text('Got it')"
        ).click(force=True)

        print(
            "\nCOOKIE POPUP CLOSED"
        )

    except:

        print(
            "\nCOOKIE POPUP NOT FOUND"
        )

    # =========================
    # FULL SEARCH ADDRESS
    # =========================

    search_address = project_address

    if city != "":

        search_address += f", {city}"

    if state != "":

        search_address += f", {state}"

    if zip_code != "":

        search_address += f" {zip_code}"

    print("\nFULL SEARCH ADDRESS:")
    print(search_address)

    # =========================
    # ADDRESS INPUT
    # =========================

    address_box = page.locator(
        "#geocoder_input"
    )

    address_box.click(force=True)

    address_box.fill(
        search_address
    )

    print("\nADDRESS ENTERED")

    # =========================
    # WAIT FOR DROPDOWN
    # =========================

    page.wait_for_timeout(3000)

    # =========================
    # TARGET ADDRESS
    # =========================

    target_compare = clean_address(
        search_address
    )

    print("\nTARGET ADDRESS:")
    print(target_compare)

    # =========================
    # KEYBOARD DROPDOWN SEARCH
    # =========================

    matched = False

    for i in range(8):

        address_box.press(
            "ArrowDown"
        )

        page.wait_for_timeout(700)

        current_value = (
            address_box.input_value()
        )

        cleaned_result = clean_address(
            current_value
        )

        similarity = SequenceMatcher(
            None,
            target_compare,
            cleaned_result
        ).ratio()

        similarity_percent = round(
            similarity * 100,
            1
        )

        print("\n--------------------")
        print(f"DROPDOWN OPTION {i + 1}")

        print("\nRAW:")
        print(current_value)

        print("\nCLEANED:")
        print(cleaned_result)

        print(
            f"\nMATCH: "
            f"{similarity_percent}%"
        )

        # =========================
        # MATCH FOUND
        # =========================

        if similarity >= 0.90:

            matched = True

            print(
                "\nMATCH FOUND"
            )

            address_box.press(
                "Enter"
            )

            print(
                "\nMATCHING ADDRESS "
                "SELECTED"
            )

            break

    # =========================
    # FAIL IF NO MATCH
    # =========================

    if matched == False:

        print("\n====================")
        print("ADDRESS MATCH FAILED")
        print("====================")

        raise Exception(
            "NO MATCHING ADDRESS FOUND "
            "IN DROPDOWN"
        )

    # =========================
    # WAIT FOR ADDRESS RESOLVE
    # =========================

    page.wait_for_timeout(4000)

    # =========================
    # GET RESOLVED ADDRESS
    # =========================

    resolved_text = page.locator(
        "#geocoder_input"
    ).input_value()

    print("\nRESOLVED ADDRESS:")
    print(resolved_text)

    # =========================
    # FINAL VALIDATION
    # =========================

    final_compare = clean_address(
        resolved_text
    )

    final_similarity = SequenceMatcher(
        None,
        target_compare,
        final_compare
    ).ratio()

    final_percent = round(
        final_similarity * 100,
        1
    )

    print("\n====================")
    print("FINAL ADDRESS VALIDATION")
    print("====================")

    print(
        f"\nFINAL MATCH PERCENT: "
        f"{final_percent}%"
    )

    if final_similarity < 0.90:

        raise Exception(
            "FINAL ADDRESS VALIDATION FAILED"
        )

    # =========================
    # SELECT RISK CATEGORY II
    # =========================

    page.locator(
        "#risk-level-selector"
    ).select_option("II")

    print(
        "\nRISK CATEGORY II SELECTED"
    )

    # =========================
    # WAIT
    # =========================

    page.wait_for_timeout(1000)

    # =========================
    # CLICK SELECT ALL
    # =========================

    page.locator(
        "#criteria > div.criteria-container__content.white.margin--small > div:nth-child(4) > div.criteria-title-item > a"
    ).click(force=True)

    print(
        "\nSELECT ALL CLICKED"
    )

    # =========================
    # WAIT
    # =========================

    page.wait_for_timeout(1000)

    # =========================
    # CLICK VIEW RESULTS
    # =========================

    page.locator(
        "text=View Results"
    ).click(force=True)

    print(
        "\nVIEW RESULTS CLICKED"
    )

    # =========================
    # WAIT FOR RESULTS PAGE
    # =========================

    print(
        "\nWAITING FOR RESULTS PAGE..."
    )

    page.wait_for_timeout(10000)

    # =========================
    # WAIT FOR FULL REPORT
    # =========================

    page.wait_for_selector(
        "text=Full Report",
        timeout=240000
    )

    print(
        "\nFULL REPORT BUTTON FOUND"
    )

    # =========================
    # DOWNLOAD FULL REPORT
    # =========================

    with page.expect_download(
        timeout=240000
    ) as download_info:

        page.get_by_text(
            "Full Report",
            exact=True
        ).click(force=True)

    download = download_info.value

    print(
        "\nDOWNLOAD COMPLETE"
    )

    # =========================
    # HANDLE EXISTING PDF
    # =========================

    base_name = os.path.splitext(
        final_pdf_name
    )[0]

    extension = ".pdf"

    counter = 2

    new_final_pdf_path = (
        final_pdf_path
    )

    while os.path.exists(
        new_final_pdf_path
    ):

        new_final_pdf_path = (
            os.path.join(
                calculations_folder,
                f"{base_name} "
                f"({counter})"
                f"{extension}"
            )
        )

        counter += 1

    # =========================
    # SAVE PDF
    # =========================

    download.save_as(
        new_final_pdf_path
    )

    print("\nPDF SAVED")

# =========================
# COMPLETE
# =========================

print("\n====================")
print("ASCE COMPLETE")
print("====================")

print("\n\nDONE\n\n")