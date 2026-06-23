from playwright.sync_api import sync_playwright
import os
import sys
import time
import ctypes
import re

# =========================
# OPTIONAL SETTINGS
# =========================

MANUAL_TOT_CONFIRM = True

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

for folder in os.listdir(year_folder):

    if folder.startswith(project_number):

        project_root = os.path.join(
            year_folder,
            folder
        )

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
verified_apn = ""
verified_project_address = ""

tot_status = "N"

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

    if line.startswith("VERIFIED_APN="):

        verified_apn = (
            line.replace(
                "VERIFIED_APN=",
                ""
            ).strip()
        )

# =========================
# SEARCH VALUE
# =========================

if verified_apn != "":

    search_value = verified_apn

    print("\nUSING VERIFIED APN")

else:

    search_value = project_address

    print("\nUSING PROJECT ADDRESS")

print(search_value)

# =========================
# WEBSITE
# =========================

website = (
    "https://www.townoftruckee.com/200/Snow-Load-Design"
)

# =========================
# PLAYWRIGHT
# =========================

with sync_playwright() as p:

    browser = p.chromium.launch(
        headless=False
    )

    page = browser.new_page()

    # =========================
    # OPEN WEBSITE
    # =========================

    page.goto(
        website,
        wait_until="domcontentloaded",
        timeout=60000
    )

    print("\nWEBSITE OPENED")

    # =========================
    # WAIT FOR PAGE
    # =========================

    time.sleep(5)

    # =========================
    # FIND FRAME
    # =========================

    target_frame = None

    frame_found = False

    for attempt in range(20):

        frames = page.frames

        print(
            f"\nFRAME SEARCH ATTEMPT "
            f"{attempt + 1}"
        )

        print(
            f"FRAME COUNT: {len(frames)}"
        )

        for frame in frames:

            try:

                popup_button = frame.locator(
                    'div.jimu-popup-action-btn'
                )

                button_count = (
                    popup_button.count()
                )

                print(
                    f"FRAME BUTTON COUNT: "
                    f"{button_count}"
                )

                if button_count > 0:

                    target_frame = frame

                    frame_found = True

                    break

            except:

                pass

        if frame_found:

            break

        time.sleep(1)

    if target_frame == None:

        raise Exception(
            "TARGET FRAME NOT FOUND"
        )

    # =========================
    # CLOSE POPUP
    # =========================

    popup_button = target_frame.locator(
        'div.jimu-popup-action-btn'
    )

    popup_button.first.click(
        force=True,
        timeout=5000
    )

    print("\nPOPUP CLOSED")

    # =========================
    # SEARCH
    # =========================

    search_success = False

    try:

        target_frame.wait_for_selector(
            '#esri_dijit_Search_0_input',
            timeout=15000
        )

        search_box = target_frame.locator(
            '#esri_dijit_Search_0_input'
        )

        search_box.scroll_into_view_if_needed()

        search_box.click(
            force=True
        )

        time.sleep(1)

        search_box.fill(
            search_value
        )

        print(
            "\nSEARCH VALUE TYPED"
        )

        time.sleep(1)

        search_box.press(
            "Enter"
        )

        search_success = True

        print(
            "\nSEARCH SUBMITTED"
        )

    except Exception as e:

        print(
            "\nSEARCH FAILED"
        )

        print(e)

    # =========================
    # STOP IF SEARCH FAILED
    # =========================

    if search_success == False:

        raise Exception(
            "TOT SEARCH FAILED"
        )

    # =========================
    # WAIT FOR RESULTS
    # =========================

    time.sleep(8)

    # =========================
    # PAGE TEXT
    # =========================

    page_text = target_frame.locator(
        "body"
    ).inner_text()

    # =========================
    # CHECK NO RESULTS
    # =========================

    no_results_found = False

    if (
        "No results" in page_text
        or "no results" in page_text
    ):

        no_results_found = True

    # =========================
    # DETERMINE TOT
    # =========================

    if no_results_found:

        tot_status = "N"

        print(
            "\nPROJECT IS NOT TOT"
        )

    else:

        tot_status = "Y"

        print(
            "\nPROJECT IS TOT"
        )

    # =========================
    # EXTRACT TOT ADDRESS
    # =========================

    tot_verified_address = ""

    try:

        lines = page_text.split("\n")

        for line in lines:

            clean_line = re.sub(
                r"\s+",
                " ",
                line
            ).strip()

            has_number = any(
                char.isdigit()
                for char in clean_line
            )

            has_street = any(
                word in clean_line.upper()
                for word in [
                    "WAY",
                    "RD",
                    "ROAD",
                    "DR",
                    "DRIVE",
                    "LN",
                    "LANE",
                    "CT",
                    "COURT",
                    "AVE",
                    "AVENUE",
                    "BLVD",
                    "CIR",
                    "PLACE",
                    "PL"
                ]
            )

            if (
                has_number
                and has_street
                and len(clean_line) < 100
            ):

                tot_verified_address = (
                    clean_line
                )

                break

    except Exception as e:

        print(
            "\nFAILED TO EXTRACT "
            "TOT ADDRESS"
        )

        print(e)

    # =========================
    # PRINT FOUND ADDRESS
    # =========================

    if tot_verified_address != "":

        print("\nTOT FOUND ADDRESS:")
        print(tot_verified_address)

    # =========================
    # ADDRESS COMPARISON
    # =========================

    existing_address = (
        project_address.strip().lower()
    )

    found_address = (
        tot_verified_address.strip().lower()
    )

    if (
        tot_verified_address != ""
        and existing_address != found_address
    ):

        print("\n====================")
        print("ADDRESS MISMATCH")
        print("====================")

        print("\nINFO.TXT ADDRESS:")
        print(project_address)

        print("\nTOT FOUND ADDRESS:")
        print(tot_verified_address)

        use_tot_address = input(
            "\nUPDATE VERIFIED "
            "PROJECT ADDRESS "
            "IN INFO FILE? (Y/N): "
        ).strip().upper()

        if use_tot_address == "Y":

            verified_project_address = (
                tot_verified_address
            )

            print(
                "\nVERIFIED PROJECT "
                "ADDRESS UPDATED"
            )

        else:

            print(
                "\nKEEPING EXISTING "
                "PROJECT ADDRESS"
            )

    # =========================
    # OPTIONAL MANUAL CONFIRM
    # =========================

    if MANUAL_TOT_CONFIRM:

        print("\n====================")
        print("VERIFY TOT STATUS")
        print("====================")

        print(
            f"\nCURRENT TOT STATUS: "
            f"{tot_status}"
        )

        confirm_tot = input(
            "\nIS THIS TOT STATUS "
            "CORRECT? (Y/N): "
        ).strip().upper()

        if confirm_tot == "N":

            if tot_status == "Y":

                tot_status = "N"

                print(
                    "\nTOT STATUS CHANGED "
                    "TO NOT TOT"
                )

            else:

                tot_status = "Y"

                print(
                    "\nTOT STATUS CHANGED "
                    "TO TOT"
                )

        else:

            print(
                "\nTOT STATUS CONFIRMED"
            )

# =========================
# UPDATE INFO FILE
# =========================

updated_lines = []

for line in info_lines:

    if line.startswith("TOT="):

        updated_lines.append(
            f"TOT={tot_status}\n"
        )

    elif line.startswith(
        "VERIFIED_PROJECT_ADDRESS="
    ):

        updated_lines.append(
            f"VERIFIED_PROJECT_ADDRESS="
            f"{verified_project_address}\n"
        )

    else:

        updated_lines.append(line)

# =========================
# WRITE INFO FILE
# =========================

with open(
    info_path,
    "w",
    encoding="utf-8"
) as file:

    file.writelines(updated_lines)

# =========================
# COMPLETE
# =========================

print("\n====================")
print("TOT COMPLETE")
print("====================")

print(f"\nFINAL TOT STATUS: {tot_status}")

print("\nVERIFIED PROJECT ADDRESS:")
print(verified_project_address)

# =========================
# FINAL TOT REMINDER
# =========================

if tot_status == "Y":

    print("\n====================")
    print("TOT REMINDER")
    print("====================")

    print(
        "\nNEED TO EXTRACT "
        "SNOW LOAD INFO "
        "FROM WEBSITE"
    )

    print(
        "\nSCREENSHOT OR "
        "PRINT WEBSITE PDF"
    )

time.sleep(1)

ctypes.windll.user32.SetForegroundWindow(
    ctypes.windll.kernel32.GetConsoleWindow()
)

print("\n\nDONE\n\n")