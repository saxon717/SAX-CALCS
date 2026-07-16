"""
diagnose_monday.py — figure out WHY items are missing contracts / locations
============================================================================
Read-only by default. Writes a log file you can work through.

WHAT IT CHECKS, per Monday item:

  CONTRACTS (items with nothing in the "Contract" column):
    - NO FOLDER MATCH            -> couldn't match the item to a computer folder
    - NO CONTRACT FOLDER         -> folder has no CONTRACT subfolder
    - CONTRACT FOLDER EMPTY      -> subfolder exists but is empty
    - HAS PDF                    -> a PDF is sitting there (should have uploaded)
    - HAS NON-PDF DOC            -> only a non-PDF file (e.g. .docx) — could be
                                    uploaded as the contract regardless of name

  LOCATIONS (items with a blank Location column):
    - NO FOLDER MATCH
    - NO INFO FILE
    - HAS ADDRESS (geocode likely failed) -> shows the address it found
    - NO ADDRESS / BAD TEMPLATE PDF       -> contract PDF has no parseable "RE:" address
    - NO ADDRESS / GOOD TEMPLATE          -> PDF looked normal but address came out blank

USAGE (from the CALCS folder):
    python diagnose_monday.py                  # report only -> writes monday_diagnosis.txt
    python diagnose_monday.py --fix-contracts  # ALSO upload the found file (PDF or not)
                                               #   to the Contract column, regardless of name

Log file: C:\\Users\\saxon\\OneDrive\\Documents\\PDF_AUTOMATION\\monday_diagnosis.txt
Throwaway utility — delete it when you're done.
"""

import os
import re
import sys
import json
import mimetypes
import difflib
import requests

from monday_config import MONDAY_API_KEY, BOARD_NAME
from config import (
    BASE_FOLDER,
    YEAR_FOLDER_SUFFIX,
    CONTRACT_SUBFOLDER,
    read_info,
)

FIX_CONTRACTS = "--fix-contracts" in sys.argv

CONTRACT_COLUMN_TITLE = "Contract"
LOCATION_COLUMN_TITLE = "Location"
LOG_PATH = r"C:\Users\saxon\OneDrive\Documents\PDF_AUTOMATION\monday_diagnosis.txt"

MONDAY_API_URL  = "https://api.monday.com/v2"
MONDAY_FILE_URL = "https://api.monday.com/v2/file"
HEADERS = {"Authorization": MONDAY_API_KEY, "API-Version": "2023-10"}

PROJECT_NUM_RE    = re.compile(r"(\d{2}-\d{3,})")
NAME_MATCH_CUTOFF = 0.60


# =========================
# MONDAY
# =========================

def monday_query(query, variables=None):
    resp = requests.post(MONDAY_API_URL, headers=HEADERS,
                         json={"query": query, "variables": variables or {}})
    if resp.status_code != 200:
        raise Exception(f"MONDAY API FAILED: {resp.status_code} {resp.text[:200]}")
    data = resp.json()
    if "errors" in data:
        raise Exception(f"MONDAY GRAPHQL ERROR: {data['errors']}")
    return data["data"]


def find_board_and_columns():
    data = monday_query("query { boards(limit:100){ id name columns{ id title } } }")
    for b in data["boards"]:
        if b["name"].strip().lower() == BOARD_NAME.strip().lower():
            cid = lid = ""
            for c in b["columns"]:
                t = c["title"].strip().lower()
                if t == CONTRACT_COLUMN_TITLE.strip().lower():
                    cid = c["id"]
                if t == LOCATION_COLUMN_TITLE.strip().lower():
                    lid = c["id"]
            if not cid:
                raise Exception(f"'{CONTRACT_COLUMN_TITLE}' column not found")
            if not lid:
                raise Exception(f"'{LOCATION_COLUMN_TITLE}' column not found")
            return b["id"], cid, lid
    raise Exception(f"MONDAY BOARD NOT FOUND: {BOARD_NAME}")


def fetch_all_items(board_id, contract_col, location_col):
    items = []

    def collect(page):
        for it in page["items"]:
            has_contract = False
            location_txt = ""
            for cv in (it.get("column_values") or []):
                if cv["id"] == contract_col:
                    if cv.get("value"):
                        try:
                            has_contract = len(json.loads(cv["value"]).get("files", [])) > 0
                        except Exception:
                            has_contract = bool(cv.get("text"))
                if cv["id"] == location_col:
                    location_txt = (cv.get("text") or "").strip()
            items.append({
                "id": it["id"], "name": it["name"],
                "has_contract": has_contract, "location": location_txt,
            })

    cols = [contract_col, location_col]
    data = monday_query("""
    query ($board_id:[ID!], $cols:[String!]) {
      boards(ids:$board_id){ items_page(limit:100){ cursor
        items{ id name column_values(ids:$cols){ id text value } } } }
    }""", {"board_id": [board_id], "cols": cols})
    page = data["boards"][0]["items_page"]
    collect(page)
    cursor = page["cursor"]
    while cursor:
        nxt = monday_query("""
        query ($cursor:String!, $cols:[String!]) {
          next_items_page(cursor:$cursor, limit:100){ cursor
            items{ id name column_values(ids:$cols){ id text value } } }
        }""", {"cursor": cursor, "cols": cols})
        page = nxt["next_items_page"]
        collect(page)
        cursor = page["cursor"]
    return items


def upload_to_column(item_id, column_id, file_path, file_name):
    mime = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    q = (f'mutation ($file: File!) {{ add_file_to_column('
         f'item_id: {item_id}, column_id: "{column_id}", file: $file) {{ id }} }}')
    with open(file_path, "rb") as fh:
        resp = requests.post(MONDAY_FILE_URL,
                             headers={"Authorization": MONDAY_API_KEY},
                             data={"query": q},
                             files={"variables[file]": (file_name, fh, mime)})
    if resp.status_code != 200:
        raise Exception(f"UPLOAD FAILED: {resp.status_code} {resp.text[:200]}")
    data = resp.json()
    if "errors" in data:
        raise Exception(f"UPLOAD ERROR: {data['errors']}")


# =========================
# LOCAL MATCHING
# =========================

def build_local_index():
    projects = []
    if not os.path.isdir(BASE_FOLDER):
        raise Exception(f"BASE FOLDER NOT FOUND: {BASE_FOLDER}")
    for yf in sorted(os.listdir(BASE_FOLDER)):
        if not yf.endswith(YEAR_FOLDER_SUFFIX):
            continue
        yp = os.path.join(BASE_FOLDER, yf)
        if not os.path.isdir(yp):
            continue
        for folder in sorted(os.listdir(yp)):
            pp = os.path.join(yp, folder)
            if not os.path.isdir(pp):
                continue
            m = PROJECT_NUM_RE.search(folder)
            number = m.group(1) if m else ""
            nk = folder.lower()
            if number:
                nk = nk.replace(number.lower(), "")
            nk = nk.strip().lstrip("-").strip()
            projects.append({"root": pp, "folder": folder, "number": number, "name_key": nk})
    return projects


def match_folder(item_name, local_index, num_index):
    m = PROJECT_NUM_RE.search(item_name)
    number = m.group(1) if m else ""
    if number and number in num_index:
        return num_index[number]
    ik = item_name.lower()
    if number:
        ik = ik.replace(number.lower(), "")
    ik = ik.strip().lstrip("-").strip()
    if not ik:
        return None
    best, ratio = None, 0.0
    for p in local_index:
        if not p["name_key"]:
            continue
        r = difflib.SequenceMatcher(None, ik, p["name_key"]).ratio()
        if r > ratio:
            best, ratio = p, r
    return best if best and ratio >= NAME_MATCH_CUTOFF else None


# =========================
# CONTRACT FOLDER INSPECTION
# =========================

def inspect_contract_folder(project_root):
    """Return (status, candidate_path, candidate_name)."""
    cf = os.path.join(project_root, CONTRACT_SUBFOLDER)
    if not os.path.isdir(cf):
        return "NO CONTRACT FOLDER", None, None
    files = [f for f in os.listdir(cf)
             if os.path.isfile(os.path.join(cf, f)) and not f.startswith("~")]
    if not files:
        return "CONTRACT FOLDER EMPTY", None, None
    pdfs = [f for f in files if f.lower().endswith(".pdf")]
    if pdfs:
        best = max(pdfs, key=lambda f: os.path.getmtime(os.path.join(cf, f)))
        return "HAS PDF", os.path.join(cf, best), best
    best = max(files, key=lambda f: os.path.getmtime(os.path.join(cf, f)))
    return "HAS NON-PDF DOC", os.path.join(cf, best), best


# =========================
# LOCATION / ADDRESS INSPECTION
# =========================

def address_from_info(project_root, project_number):
    try:
        info, path = read_info(project_root, project_number)
    except Exception:
        return None, ""
    if not path:
        return None, ""
    v = info.get("VERIFIED_PROJECT_ADDRESS", "").strip()
    if v:
        return path, v
    street = info.get("PROJECT_ADDRESS", "").strip() or info.get("MANUAL_PROJECT_ADDRESS", "").strip()
    if not street:
        return path, ""
    parts = [street]
    if info.get("CITY", "").strip():
        parts.append(info["CITY"].strip())
    tail = " ".join(x for x in [info.get("STATE", "").strip(), info.get("ZIP_CODE", "").strip()] if x)
    if tail:
        parts.append(tail)
    return path, ", ".join(parts)


def contract_template_ok(project_root):
    """Parse the contract PDF's RE: line. Return 'GOOD' / 'BAD' / 'NO PDF'."""
    cf = os.path.join(project_root, CONTRACT_SUBFOLDER)
    if not os.path.isdir(cf):
        return "NO PDF"
    pdf = ""
    for f in os.listdir(cf):
        if f.lower().endswith(".pdf") and not f.startswith("~"):
            pdf = os.path.join(cf, f)
            break
    if not pdf:
        return "NO PDF"
    try:
        import pdfplumber
        text = ""
        with pdfplumber.open(pdf) as p:
            for pg in p.pages:
                ex = pg.extract_text()
                if ex:
                    text += ex + "\n"
    except Exception:
        return "BAD"
    text = re.sub(r"\(cid:\d+\)", "", text)
    lines = text.split("\n")
    lower = [l.lower().strip() for l in lines]
    for i, line in enumerate(lower):
        if "re:" in line:
            for j in range(i, min(i + 10, len(lines))):
                cand = lines[j].strip()
                if any(c.isdigit() for c in cand) and "," in cand and len(cand.split(",")) >= 3:
                    return "GOOD"
    return "BAD"


# =========================
# MAIN
# =========================

def main():
    print("Connecting to Monday...")
    board_id, contract_col, location_col = find_board_and_columns()
    items = fetch_all_items(board_id, contract_col, location_col)
    print(f"  {len(items)} items on board '{BOARD_NAME}'")

    local_index = build_local_index()
    num_index = {p["number"]: p for p in local_index if p["number"]}

    contract_rows = []   # (item_name, status, candidate_name)
    location_rows = []   # (item_name, reason, detail)
    uploaded = []

    for it in items:
        proj = match_folder(it["name"], local_index, num_index)

        # ---- CONTRACT ----
        if not it["has_contract"]:
            if not proj:
                contract_rows.append((it["name"], "NO FOLDER MATCH", ""))
            else:
                status, cand_path, cand_name = inspect_contract_folder(proj["root"])
                contract_rows.append((it["name"], status, cand_name or ""))
                if FIX_CONTRACTS and cand_path:
                    try:
                        upload_to_column(it["id"], contract_col, cand_path, cand_name)
                        uploaded.append((it["name"], cand_name))
                        print(f"[UPLOADED] {it['name']}  <-  {cand_name}")
                    except Exception as e:
                        print(f"[UPLOAD ERROR] {it['name']}: {e}")

        # ---- LOCATION ----
        if not it["location"]:
            if not proj:
                location_rows.append((it["name"], "NO FOLDER MATCH", ""))
            else:
                info_path, addr = address_from_info(proj["root"], proj["number"])
                if info_path is None:
                    location_rows.append((it["name"], "NO INFO FILE", ""))
                elif addr:
                    location_rows.append((it["name"], "HAS ADDRESS (geocode likely failed)", addr))
                else:
                    tmpl = contract_template_ok(proj["root"])
                    if tmpl == "GOOD":
                        location_rows.append((it["name"], "NO ADDRESS / GOOD TEMPLATE", ""))
                    elif tmpl == "NO PDF":
                        location_rows.append((it["name"], "NO ADDRESS / NO PDF", ""))
                    else:
                        location_rows.append((it["name"], "NO ADDRESS / BAD TEMPLATE PDF", ""))

    # ---- write log ----
    def count_by(rows, idx):
        d = {}
        for r in rows:
            d[r[idx]] = d.get(r[idx], 0) + 1
        return d

    lines = []
    lines.append("=" * 70)
    lines.append("MONDAY DIAGNOSIS")
    lines.append("=" * 70)
    lines.append(f"Total items: {len(items)}")
    lines.append("")

    lines.append("-" * 70)
    lines.append(f"MISSING CONTRACT: {len(contract_rows)}")
    lines.append("-" * 70)
    for k, v in sorted(count_by(contract_rows, 1).items(), key=lambda x: -x[1]):
        lines.append(f"  {v:>4}  {k}")
    lines.append("")
    for name, status, cand in sorted(contract_rows, key=lambda r: (r[1], r[0].lower())):
        extra = f"   candidate: {cand}" if cand else ""
        lines.append(f"  [{status}] {name}{extra}")
    lines.append("")

    lines.append("-" * 70)
    lines.append(f"MISSING LOCATION: {len(location_rows)}")
    lines.append("-" * 70)
    for k, v in sorted(count_by(location_rows, 1).items(), key=lambda x: -x[1]):
        lines.append(f"  {v:>4}  {k}")
    lines.append("")
    for name, reason, detail in sorted(location_rows, key=lambda r: (r[1], r[0].lower())):
        extra = f"   -> {detail}" if detail else ""
        lines.append(f"  [{reason}] {name}{extra}")
    lines.append("")

    if FIX_CONTRACTS:
        lines.append("-" * 70)
        lines.append(f"UPLOADED THIS RUN: {len(uploaded)}")
        lines.append("-" * 70)
        for name, cand in uploaded:
            lines.append(f"  {name}  <-  {cand}")
        lines.append("")

    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # ---- console summary ----
    print("\n" + "=" * 55)
    print("SUMMARY")
    print("=" * 55)
    print(f"Missing contract:  {len(contract_rows)}")
    for k, v in sorted(count_by(contract_rows, 1).items(), key=lambda x: -x[1]):
        print(f"    {v:>4}  {k}")
    print(f"Missing location:  {len(location_rows)}")
    for k, v in sorted(count_by(location_rows, 1).items(), key=lambda x: -x[1]):
        print(f"    {v:>4}  {k}")
    if FIX_CONTRACTS:
        print(f"Uploaded this run: {len(uploaded)}")
    print(f"\nFull log written to:\n  {LOG_PATH}")
    print("Done.")


if __name__ == "__main__":
    main()
