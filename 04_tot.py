from playwright.sync_api import sync_playwright
import os
import sys
import time
import re

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
year_prefix = project_number[:2]

year_folder = os.path.join(
    base_folder,
    f"{year_prefix}-XXX"
)

# =========================
# FIND PROJECT
# =========================

print("UI_STEP:Reading INFO file")
sys.stdout.flush()

project_root = ""

for folder in os.listdir(year_folder):
    if folder.startswith(project_number):
        project_root = os.path.join(year_folder, folder)
        break

if project_root == "":
    raise Exception("PROJECT NOT FOUND")

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
        full_path = os.path.join(archive_folder, file)
        modified_time = os.path.getmtime(full_path)
        if modified_time > latest_time:
            latest_time = modified_time
            info_path = full_path

if info_path == "":
    raise Exception("INFO FILE NOT FOUND")

print("INFO FILE FOUND")

# =========================
# READ INFO FILE
# =========================

with open(info_path, "r", encoding="utf-8") as file:
    info_lines = file.readlines()

# =========================
# EXTRACT INFO
# =========================

project_address = ""
verified_apn    = ""
verified_project_address = ""
tot_status = "N"

for line in info_lines:
    if line.startswith("PROJECT_ADDRESS="):
        project_address = line.replace(
            "PROJECT_ADDRESS=", ""
        ).strip()
    if line.startswith("VERIFIED_APN="):
        verified_apn = line.replace(
            "VERIFIED_APN=", ""
        ).strip()

# =========================
# SEARCH VALUE
# =========================

if verified_apn != "":
    search_value = verified_apn
    print(f"USING VERIFIED APN: {search_value}")
else:
    search_value = project_address
    print(f"USING PROJECT ADDRESS: {search_value}")

# =========================
# OPEN TOT WEBSITE
# =========================

print("UI_STEP:Opening TOT website")
sys.stdout.flush()

website = (
    "https://www.townoftruckee.com/200/Snow-Load-Design"
)

with sync_playwright() as p:

    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    page.goto(
        website,
        wait_until="domcontentloaded",
        timeout=60000
    )

    print("WEBSITE OPENED")
    time.sleep(5)

    # =========================
    # FIND FRAME
    # =========================

    print("UI_STEP:Searching address")
    sys.stdout.flush()

    target_frame = None
    frame_found  = False

    for attempt in range(20):
        frames = page.frames
        for frame in frames:
            try:
                popup_button = frame.locator(
                    'div.jimu-popup-action-btn'
                )
                if popup_button.count() > 0:
                    target_frame = frame
                    frame_found  = True
                    break
            except:
                pass
        if frame_found:
            break
        time.sleep(1)

    if target_frame is None:
        raise Exception("TARGET FRAME NOT FOUND")

    # Close popup
    popup_button = target_frame.locator(
        'div.jimu-popup-action-btn'
    )
    popup_button.first.click(force=True, timeout=5000)
    print("POPUP CLOSED")

    # Search
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
        search_box.click(force=True)
        time.sleep(1)
        search_box.fill(search_value)
        print("SEARCH VALUE TYPED")
        time.sleep(1)
        search_box.press("Enter")
        search_success = True
        print("SEARCH SUBMITTED")
    except Exception as e:
        print(f"SEARCH FAILED: {e}")

    if not search_success:
        raise Exception("TOT SEARCH FAILED")

    # =========================
    # WAIT FOR RESULTS
    # =========================

    print("UI_STEP:Detecting TOT status")
    sys.stdout.flush()

    time.sleep(8)

    page_text = target_frame.locator("body").inner_text()

    no_results_found = (
        "No results" in page_text
        or "no results" in page_text
    )

    if no_results_found:
        tot_status = "N"
        print("PROJECT IS NOT TOT")
    else:
        tot_status = "Y"
        print("PROJECT IS TOT")

    # =========================
    # EXTRACT TOT ADDRESS
    # =========================

    tot_verified_address = ""

    try:
        for line in page_text.split("\n"):
            clean_line = re.sub(
                r"\s+", " ", line
            ).strip()
            has_number = any(
                char.isdigit() for char in clean_line
            )
            has_street = any(
                word in clean_line.upper()
                for word in [
                    "WAY", "RD", "ROAD", "DR", "DRIVE",
                    "LN", "LANE", "CT", "COURT", "AVE",
                    "AVENUE", "BLVD", "CIR", "PLACE", "PL"
                ]
            )
            if has_number and has_street and len(clean_line) < 100:
                tot_verified_address = clean_line
                break
    except Exception as e:
        print(f"FAILED TO EXTRACT TOT ADDRESS: {e}")

    if tot_verified_address != "":
        print(f"TOT FOUND ADDRESS: {tot_verified_address}")

    # =========================
    # ADDRESS MISMATCH CHECK
    # =========================

    existing_address = project_address.strip().lower()
    found_address    = tot_verified_address.strip().lower()

    if (
        tot_verified_address != ""
        and existing_address != found_address
    ):
        print("ADDRESS MISMATCH DETECTED")
        print(f"UI_ADDRESS_MISMATCH:{project_address}|{tot_verified_address}")
        sys.stdout.flush()

        response = sys.stdin.readline().strip()

        if response == "Y":
            verified_project_address = tot_verified_address
            print("VERIFIED PROJECT ADDRESS UPDATED")
        else:
            print("KEEPING EXISTING PROJECT ADDRESS")

    # =========================
    # CONFIRM TOT STATUS
    # =========================

    print("UI_STEP:Confirming TOT status")
    sys.stdout.flush()

    print(f"UI_CONFIRM_TOT:{tot_status}")
    sys.stdout.flush()

    response = sys.stdin.readline().strip()

    if response == "OVERRIDE":
        if tot_status == "Y":
            tot_status = "N"
            print("TOT STATUS CHANGED TO NOT TOT")
        else:
            tot_status = "Y"
            print("TOT STATUS CHANGED TO TOT")
    elif response == "CONFIRMED":
        print("TOT STATUS CONFIRMED")
    else:
        print("TOT CONFIRMATION CANCELLED — keeping detected status")

# =========================
# UPDATE INFO FILE
# =========================

print("UI_STEP:Updating INFO file")
sys.stdout.flush()

updated_lines = []

for line in info_lines:
    if line.startswith("TOT="):
        updated_lines.append(f"TOT={tot_status}\n")
    elif line.startswith("VERIFIED_PROJECT_ADDRESS="):
        updated_lines.append(
            f"VERIFIED_PROJECT_ADDRESS="
            f"{verified_project_address}\n"
        )
    else:
        updated_lines.append(line)

with open(info_path, "w", encoding="utf-8") as file:
    file.writelines(updated_lines)

# =========================
# COMPLETE
# =========================

print(f"FINAL TOT STATUS: {tot_status}")
print(f"VERIFIED PROJECT ADDRESS: {verified_project_address}")

if tot_status == "Y":
    print("TOT REMINDER: EXTRACT SNOW LOAD INFO FROM WEBSITE")
    print("SCREENSHOT OR PRINT WEBSITE PDF")

print("DONE")