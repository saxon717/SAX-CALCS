import os
import shutil
from datetime import datetime

# =========================
# BASE PATHS
# =========================

BASE_FOLDER = (
    r"C:\Users\saxon\Dropbox\SHEAR FORCE"
    r"\1) CURRENT PROJECTS"
)

TEMPLATE_FOLDER = (
    r"C:\Users\saxon\Dropbox\SHEAR FORCE"
    r"\4) TEMPLATES\CALC EXCEL TEMPLATES"
)

TOT_TEMPLATE_FOLDER = (
    r"C:\Users\saxon\Dropbox\SHEAR FORCE"
    r"\4) TEMPLATES\CALC EXCEL TEMPLATES\ASCE-7-16 TEMPLATES"
)

SAX_TEMPLATE_FOLDER = (
    r"C:\Users\saxon\Dropbox\SHEAR FORCE"
    r"\4) TEMPLATES\SAX UI"
)

# =========================
# PROJECT SUBFOLDERS
# =========================

UI_SUBFOLDER       = "UI"
ARCHIVE_SUBFOLDER  = os.path.join("UI", "ARCHIVE")
CONTRACT_SUBFOLDER = "CONTRACT"
CALC_SUBFOLDER     = "CALCULATIONS"

# =========================
# TEMPLATE FILENAMES
# =========================

LAT_TEMPLATE_NAME      = "SF Lateral Design Template"   # partial match
VERT_TEMPLATE_NAME     = "SF Vertical Package Template" # partial match
UI_LOG_NAME            = "UI INTEGRATION LOG.xlsx"
TOT_LAT_TEMPLATE_NAME  = "LAT XL"                      # partial match
TOT_VERT_TEMPLATE_NAME = "VERT XL"                     # partial match

# =========================
# WEBSITES
# =========================

TOT_WEBSITE       = "https://www.townoftruckee.com/200/Snow-Load-Design"
ELEVATION_WEBSITE = "https://whatismyelevation.com/"
SEISMIC_WEBSITE   = "https://www.seismicmaps.org/"

# =========================
# YEAR FOLDER FORMAT
# =========================

YEAR_FOLDER_SUFFIX = "-XXX"

# =========================
# BROWSER SETTINGS
# =========================

HEADLESS = False  # True = run in background, False = show browser

# =========================
# DATE HELPER
# =========================

def today_str():
    t = datetime.now()
    return f"{t.month}.{t.day}.{str(t.year)[2:]}"

# =========================
# PROJECT HELPERS
# =========================

def find_project(project_number):
    """Find project root folder and folder name."""
    year_prefix = project_number[:2]
    year_folder = os.path.join(BASE_FOLDER, f"{year_prefix}{YEAR_FOLDER_SUFFIX}")
    if not os.path.exists(year_folder):
        return None, None
    for folder in os.listdir(year_folder):
        if folder.startswith(project_number):
            return os.path.join(year_folder, folder), folder
    return None, None

def get_project_name(project_folder_name, project_number):
    """Extract clean project name from folder name."""
    return (
        project_folder_name
        .replace(project_number, "")
        .strip().lstrip("-").strip()
    )

def get_ui_folder(project_root):
    """Return UI folder path, creating it if needed."""
    path = os.path.join(project_root, UI_SUBFOLDER)
    os.makedirs(path, exist_ok=True)
    return path

def get_archive_folder(project_root):
    """Return ARCHIVE folder path, creating it if needed."""
    path = os.path.join(project_root, ARCHIVE_SUBFOLDER)
    os.makedirs(path, exist_ok=True)
    return path

def get_calc_folder(project_root):
    """Return CALCULATIONS folder path."""
    return os.path.join(project_root, CALC_SUBFOLDER)

# =========================
# INFO FILE HELPERS
# =========================

def find_info_file(project_root, project_number):
    """Find the most recent INFO file in the UI folder."""
    ui_folder   = get_ui_folder(project_root)
    latest_time = 0
    info_path   = ""
    for file in os.listdir(ui_folder):
        upper = file.upper()
        if (
            file.endswith(".txt")
            and "INFO" in upper
            and project_number in upper
            and not file.startswith("~")
        ):
            full_path = os.path.join(ui_folder, file)
            t         = os.path.getmtime(full_path)
            if t > latest_time:
                latest_time = t
                info_path   = full_path
    return info_path

def read_info(project_root, project_number):
    """Read INFO file and return dict of all key=value pairs."""
    info_path = find_info_file(project_root, project_number)
    if not info_path:
        return {}, ""
    data = {}
    with open(info_path, "r", encoding="utf-8") as f:
        for line in f:
            if "=" in line:
                key, _, val = line.partition("=")
                data[key.strip()] = val.strip()
    return data, info_path

def update_info(info_path, project_root, fields_dict):
    """
    Update specific fields in INFO file.
    Archives old file, saves new one with today's date.
    fields_dict: {KEY: value} — only updates specified keys.
    """
    if not info_path or not os.path.exists(info_path):
        return info_path

    # Read existing lines
    with open(info_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Update fields
    updated = []
    for line in lines:
        if "=" in line:
            key = line.partition("=")[0].strip()
            if key + "=" in fields_dict or key in fields_dict:
                k = key if key in fields_dict else key + "="
                val = fields_dict.get(k, fields_dict.get(key + "=", ""))
                updated.append(f"{key}={val}\n")
                # Remove from dict so we know what's been handled
                fields_dict.pop(k, None)
                fields_dict.pop(key, None)
                fields_dict.pop(key + "=", None)
            else:
                updated.append(line)
        else:
            updated.append(line)

    # Append any remaining new fields
    for key, val in fields_dict.items():
        clean_key = key.rstrip("=")
        updated.append(f"{clean_key}={val}\n")

    # Archive old file
    archive_folder = get_archive_folder(project_root)
    old_name       = os.path.basename(info_path)
    archive_path   = os.path.join(archive_folder, old_name)
    # Avoid overwriting archive if same name
    if os.path.exists(archive_path):
        base, ext    = os.path.splitext(old_name)
        counter      = 2
        archive_path = os.path.join(archive_folder, f"{base} ({counter}){ext}")
        while os.path.exists(archive_path):
            counter     += 1
            archive_path = os.path.join(archive_folder, f"{base} ({counter}){ext}")
    shutil.copy2(info_path, archive_path)

    # Build new filename with today's date
    project_number = ""
    for line in updated:
        if line.startswith("PROJECT_NUMBER="):
            project_number = line.replace("PROJECT_NUMBER=", "").strip()
            break

    ui_folder    = get_ui_folder(project_root)
    new_filename = f"{project_number} INFO - {today_str()}.txt"
    new_path     = os.path.join(ui_folder, new_filename)

    # Remove old file
    try:
        os.remove(info_path)
    except:
        pass

    # Write new file
    with open(new_path, "w", encoding="utf-8") as f:
        f.writelines(updated)

    return new_path

def write_info_lines(info_path, project_root, lines):
    """
    Write raw lines to INFO file.
    Archives old, saves new with today's date.
    """
    # Archive old
    archive_folder = get_archive_folder(project_root)
    old_name       = os.path.basename(info_path)
    archive_path   = os.path.join(archive_folder, old_name)
    if os.path.exists(archive_path):
        base, ext    = os.path.splitext(old_name)
        counter      = 2
        archive_path = os.path.join(archive_folder, f"{base} ({counter}){ext}")
        while os.path.exists(archive_path):
            counter     += 1
            archive_path = os.path.join(archive_folder, f"{base} ({counter}){ext}")
    if os.path.exists(info_path):
        shutil.copy2(info_path, archive_path)
        try:
            os.remove(info_path)
        except:
            pass

    # Build new filename
    project_number = ""
    for line in lines:
        if line.startswith("PROJECT_NUMBER="):
            project_number = line.replace("PROJECT_NUMBER=", "").strip()
            break

    ui_folder    = get_ui_folder(project_root)
    new_filename = f"{project_number} INFO - {today_str()}.txt"
    new_path     = os.path.join(ui_folder, new_filename)

    with open(new_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    return new_path

# =========================
# TEMPLATE FINDER
# =========================

def find_template(folder, partial_name, extension=".xlsm", extra_match=None):
    """Find a template file by partial name match."""
    for file in os.listdir(folder):
        if (
            file.endswith(extension)
            and partial_name in file
            and not file.startswith("~$")
        ):
            if extra_match and extra_match not in file:
                continue
            return os.path.join(folder, file)
    return ""

# =========================
# XL FILE FINDER
# =========================

def find_xl_file(calc_folder, partial_name):
    """Find most recent XL file matching partial name."""
    latest_time = 0
    found_path  = ""
    for file in os.listdir(calc_folder):
        if (
            file.endswith(".xlsm")
            and partial_name.upper() in file.upper()
            and not file.startswith("~$")
        ):
            full_path = os.path.join(calc_folder, file)
            t         = os.path.getmtime(full_path)
            if t > latest_time:
                latest_time = t
                found_path  = full_path
    return found_path

# =========================
# OUTPUT FILE NAMER
# =========================

def make_output_path(calc_folder, project_number, project_name, suffix, extension=".xlsm"):
    """Generate unique output file path with today's date."""
    base_name = f"{project_number} {project_name} - {suffix} - {today_str()}"
    path      = os.path.join(calc_folder, f"{base_name}{extension}")
    counter   = 2
    while os.path.exists(path):
        path = os.path.join(calc_folder, f"{base_name} ({counter}){extension}")
        counter += 1
    return path