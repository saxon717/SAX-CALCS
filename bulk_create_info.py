"""
bulk_create_info.py — bulk INFO file creation for SAX (Monday-driven)
=====================================================================
Creates INFO files ONLY for projects that exist on Monday.com.

FLOW:
  1. Pull ALL items from the Monday board.
  2. Match each item to its Dropbox folder (project number, ~60% name fallback).
  3. If that project has no INFO file yet -> create one from its contract PDF.

RULES:
  - ONLY creates NEW INFO files. If one already exists -> SKIP (never touched).
  - No contract PDF -> skip.
  - No pop-ups: if address/APN can't be auto-detected, that field is left BLANK
    and the file is still created. Output format matches 01_info.py exactly.

USAGE (from the CALCS folder):
    python bulk_create_info.py --dry-run   # preview only
    python bulk_create_info.py             # create the files

Throwaway utility — delete it when you're done.
"""

import os
import re
import sys
import glob
import difflib
import requests

from monday_config import MONDAY_API_KEY, BOARD_NAME
from config import (
    BASE_FOLDER,
    YEAR_FOLDER_SUFFIX,
    CONTRACT_SUBFOLDER,
    get_project_name,
    get_ui_folder,
    today_str,
)

DRY_RUN = "--dry-run" in sys.argv

MONDAY_API_URL    = "https://api.monday.com/v2"
HEADERS           = {"Authorization": MONDAY_API_KEY, "API-Version": "2023-10"}
PROJECT_NUM_RE    = re.compile(r"(\d{2}-\d{3,})")
NAME_MATCH_CUTOFF = 0.60


# =========================
# MONDAY
# =========================

def monday_query(query, variables=None):
    resp = requests.post(
        MONDAY_API_URL, headers=HEADERS,
        json={"query": query, "variables": variables or {}},
    )
    if resp.status_code != 200:
        raise Exception(f"MONDAY API FAILED: {resp.status_code} {resp.text[:200]}")
    data = resp.json()
    if "errors" in data:
        raise Exception(f"MONDAY GRAPHQL ERROR: {data['errors']}")
    return data["data"]


def find_board_id():
    data = monday_query("query { boards(limit: 100) { id name } }")
    for board in data["boards"]:
        if board["name"].strip().lower() == BOARD_NAME.strip().lower():
            return board["id"]
    raise Exception(f"MONDAY BOARD NOT FOUND: {BOARD_NAME}")


def fetch_all_items(board_id):
    items = []
    data = monday_query("""
    query ($board_id: [ID!]) {
      boards(ids: $board_id) {
        items_page(limit: 500) { cursor items { id name } }
      }
    }
    """, {"board_id": [board_id]})
    page = data["boards"][0]["items_page"]
    items.extend(page["items"])
    cursor = page["cursor"]
    while cursor:
        nxt = monday_query("""
        query ($cursor: String!) {
          next_items_page(cursor: $cursor, limit: 500) { cursor items { id name } }
        }
        """, {"cursor": cursor})
        page = nxt["next_items_page"]
        items.extend(page["items"])
        cursor = page["cursor"]
    return items


# =========================
# LOCAL MATCHING
# =========================

def build_local_index():
    projects = []
    if not os.path.isdir(BASE_FOLDER):
        raise Exception(f"BASE FOLDER NOT FOUND: {BASE_FOLDER}")
    for year_folder in sorted(os.listdir(BASE_FOLDER)):
        if not year_folder.endswith(YEAR_FOLDER_SUFFIX):
            continue
        year_path = os.path.join(BASE_FOLDER, year_folder)
        if not os.path.isdir(year_path):
            continue
        for folder in sorted(os.listdir(year_path)):
            proj_path = os.path.join(year_path, folder)
            if not os.path.isdir(proj_path):
                continue
            m = PROJECT_NUM_RE.search(folder)
            number = m.group(1) if m else ""
            name_key = folder.lower()
            if number:
                name_key = name_key.replace(number.lower(), "")
            name_key = name_key.strip().lstrip("-").strip()
            projects.append({
                "root": proj_path, "folder": folder,
                "number": number, "name_key": name_key,
            })
    return projects


def match_folder(item_name, local_index, num_index):
    m = PROJECT_NUM_RE.search(item_name)
    number = m.group(1) if m else ""
    if number and number in num_index:
        return num_index[number]
    item_key = item_name.lower()
    if number:
        item_key = item_key.replace(number.lower(), "")
    item_key = item_key.strip().lstrip("-").strip()
    if not item_key:
        return None
    best, best_ratio = None, 0.0
    for p in local_index:
        if not p["name_key"]:
            continue
        r = difflib.SequenceMatcher(None, item_key, p["name_key"]).ratio()
        if r > best_ratio:
            best, best_ratio = p, r
    if best and best_ratio >= NAME_MATCH_CUTOFF:
        return best
    return None


# =========================
# EXTRACTION (from 01_info.py, non-interactive)
# =========================

def extract_info(contract_pdf, project_number, project_name):
    import pdfplumber

    text = ""
    with pdfplumber.open(contract_pdf) as pdf:
        for page in pdf.pages:
            ex = page.extract_text()
            if ex:
                text += ex + "\n"

    project_description = ""
    if "Project Description" in text and "Scope" in text:
        desc, capture = [], False
        for line in text.split("\n"):
            cl = line.strip()
            if "Project Description" in cl:
                capture = True
                continue
            if capture and "Scope" in cl:
                break
            if capture and cl:
                desc.append(cl)
        project_description = " ".join(desc)
    project_description = re.sub(r"\s+", " ", project_description).strip()

    text  = re.sub(r"\(cid:\d+\)", "", text)
    lines = text.split("\n")
    lower = [l.lower().strip() for l in lines]

    street_address = city = state = zip_code = county = apn = ""
    good_template = False
    try:
        for i, line in enumerate(lower):
            if "re:" in line:
                for j in range(i, min(i + 10, len(lines))):
                    cand = lines[j].strip()
                    if any(c.isdigit() for c in cand) and "," in cand:
                        parts = [p.strip() for p in cand.split(",")]
                        if len(parts) >= 3:
                            street_address = parts[0]
                            city           = parts[1]
                            sz             = parts[2]
                            sm = re.search(r"\b[A-Z]{2}\b", sz)
                            zm = re.search(r"\b\d{5}\b", sz)
                            if sm:
                                state = sm.group(0)
                            if zm:
                                zip_code = zm.group(0)
                            good_template = True
                            break
                if good_template:
                    break
    except Exception:
        pass

    for line in lines:
        ll = line.lower()
        if "county apn" in ll:
            if "placer" in ll:
                county = "PLACER"
            elif "nevada" in ll:
                county = "NEVADA"
            m = re.search(r"(\d[\d\-]{6,20}\d)", line)
            if m:
                digits = re.sub(r"\D", "", m.group(1))
                if len(digits) >= 9:
                    d = digits[:9]
                    apn = f"{d[0:3]}-{d[3:6]}-{d[6:9]}"
                elif len(digits) == 8:
                    apn = f"{digits[0:3]}-{digits[3:6]}-{digits[6:8]}"
            break

    emails = list(dict.fromkeys(re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)))
    names  = []
    for i, line in enumerate(lines):
        ll = line.lower().strip()
        if "via e-mail:" in ll or "via email:" in ll:
            for j in range(i - 1, -1, -1):
                cand = lines[j].strip()
                if not cand:
                    continue
                if "@" in cand or "proposal" in cand.lower() or "engineering" in cand.lower():
                    continue
                for sp in re.split(r",|\+| and ", cand):
                    nm = sp.strip()
                    if 2 <= len(nm.split()) <= 5 and any(c.isalpha() for c in nm):
                        names.append(nm.upper())
                break
    names = list(dict.fromkeys(names))

    return {
        "PROJECT_ADDRESS": street_address,
        "CITY": city, "STATE": state, "ZIP_CODE": zip_code,
        "COUNTY": county, "APN": apn,
        "CLIENT_NAME_1":  names[0]  if len(names)  >= 1 else "",
        "CLIENT_NAME_2":  names[1]  if len(names)  >= 2 else "",
        "CLIENT_EMAIL_1": emails[0] if len(emails) >= 1 else "",
        "CLIENT_EMAIL_2": emails[1] if len(emails) >= 2 else "",
        "PROJECT_DESCRIPTION": project_description,
        "good_template": good_template,
    }


def build_info_lines(project_number, project_name, contract_pdf, d):
    return [
        f"PROJECT_NUMBER={project_number}\n",
        f"PROJECT_NAME={project_name}\n\n",
        f"TOT=\n\n",
        f"PROJECT_ADDRESS={d['PROJECT_ADDRESS']}\n",
        f"MANUAL_PROJECT_ADDRESS=\n",
        f"CITY={d['CITY']}\n",
        f"STATE={d['STATE']}\n",
        f"ZIP_CODE={d['ZIP_CODE']}\n\n",
        f"ASCE_RESOLVED_ADDRESS=\n",
        f"VERIFIED_PROJECT_ADDRESS=\n",
        f"VERIFIED_APN=\n",
        f"VERIFIED_COUNTY=\n\n",
        f"COUNTY={d['COUNTY']}\n",
        f"APN={d['APN']}\n\n",
        f"CLIENT_NAME_1={d['CLIENT_NAME_1']}\n",
        f"CLIENT_EMAIL_1={d['CLIENT_EMAIL_1']}\n",
        f"CLIENT_NAME_2={d['CLIENT_NAME_2']}\n",
        f"CLIENT_EMAIL_2={d['CLIENT_EMAIL_2']}\n\n",
        f"PROJECT_DESCRIPTION={d['PROJECT_DESCRIPTION']}\n\n",
        f"CONTRACT_PDF={contract_pdf}\n",
        f"MONDAY_UPLOADED=\n",
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


def has_info_file(ui_folder, project_number):
    matches = [
        f for f in glob.glob(os.path.join(ui_folder, f"{project_number} INFO*.txt"))
        if not os.path.basename(f).startswith("~")
    ]
    return len(matches) > 0


def find_contract_pdf(project_root):
    cf = os.path.join(project_root, CONTRACT_SUBFOLDER)
    if not os.path.isdir(cf):
        return ""
    for f in os.listdir(cf):
        if f.lower().endswith(".pdf") and not f.startswith("~"):
            return os.path.join(cf, f)
    return ""


# =========================
# MAIN
# =========================

def main():
    mode = "DRY RUN (no files created)" if DRY_RUN else "LIVE (creating INFO files)"
    print(f"=== BULK CREATE INFO FILES (Monday-driven) — {mode} ===\n")

    print("Connecting to Monday...")
    board_id  = find_board_id()
    all_items = fetch_all_items(board_id)
    print(f"  {len(all_items)} items on board '{BOARD_NAME}'\n")

    local_index = build_local_index()
    num_index   = {p["number"]: p for p in local_index if p["number"]}

    created     = []
    no_address  = []
    skipped_has = 0
    no_folder   = []
    no_contract = []
    errors      = []

    for it in all_items:
        proj = match_folder(it["name"], local_index, num_index)
        if not proj:
            no_folder.append(it["name"])
            print(f"[NO FOLDER]    {it['name']}")
            continue

        project_number = proj["number"] or (PROJECT_NUM_RE.search(it["name"]).group(1)
                                            if PROJECT_NUM_RE.search(it["name"]) else "")
        project_name   = get_project_name(proj["folder"], project_number)

        ui_folder = get_ui_folder(proj["root"])
        if project_number and has_info_file(ui_folder, project_number):
            skipped_has += 1
            continue

        contract_pdf = find_contract_pdf(proj["root"])
        if not contract_pdf:
            no_contract.append(f"{it['name']}  ->  {proj['folder']}")
            print(f"[NO CONTRACT]  {it['name']}  (folder: {proj['folder']})")
            continue

        try:
            d = extract_info(contract_pdf, project_number, project_name)
            if not d["good_template"]:
                no_address.append(it["name"])

            if DRY_RUN:
                tag = "" if d["good_template"] else "  (address blank)"
                print(f"[WOULD CREATE] {it['name']}{tag}")
                created.append(it["name"])
                continue

            lines    = build_info_lines(project_number, project_name, contract_pdf, d)
            filename = f"{project_number} INFO - {today_str()}.txt"
            out_path = os.path.join(ui_folder, filename)
            with open(out_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            tag = "" if d["good_template"] else "  (address blank)"
            print(f"[CREATED]      {it['name']}{tag}")
            created.append(it["name"])

        except Exception as e:
            errors.append((it["name"], str(e)))
            print(f"[ERROR]        {it['name']}: {e}")

    # --- Summary ---
    print("\n" + "=" * 55)
    print("SUMMARY")
    print("=" * 55)
    verb = "Would create" if DRY_RUN else "Created"
    print(f"{verb}:               {len(created)}")
    print(f"Skipped (has INFO):    {skipped_has}")
    print(f"No folder match:       {len(no_folder)}")
    print(f"No contract PDF:       {len(no_contract)}")
    print(f"Address left blank:    {len(no_address)}")
    print(f"Errors:                {len(errors)}")

    if no_folder:
        print("\nMonday items with NO folder match:")
        for n in no_folder:
            print(f"  - {n}")
    if no_contract:
        print("\nMatched a folder but NO contract PDF:")
        for n in no_contract:
            print(f"  - {n}")
    if no_address:
        print("\nCreated but address NOT auto-detected (fill later):")
        for n in no_address:
            print(f"  - {n}")
    if errors:
        print("\nErrors:")
        for n, e in errors:
            print(f"  - {n}: {e}")
    print("\nDone.")


if __name__ == "__main__":
    main()