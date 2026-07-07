# =========================
# SAX CONFIG
# All paths, folder names, templates, and URLs.
# Change here — updates everywhere.
# =========================

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
CONTRACT_SUBFOLDER = "CONTRACT"
CALC_SUBFOLDER     = "CALCULATIONS"

# =========================
# TEMPLATE FILENAMES
# =========================

LAT_TEMPLATE_NAME      = "SF Lateral Design Template 3.28.26.xlsm"
VERT_TEMPLATE_NAME     = "SF Vertical Package Template"   # partial match
UI_LOG_NAME            = "UI INTEGRATION LOG.xlsx"
TOT_LAT_TEMPLATE_NAME  = "LAT XL"          # partial match — finds any file containing this
TOT_VERT_TEMPLATE_NAME = "VERT XL"         # partial match — finds any file containing this

# =========================
# WEBSITES
# =========================

TOT_WEBSITE       = "https://www.townoftruckee.com/200/Snow-Load-Design"
ELEVATION_WEBSITE = "https://whatismyelevation.com/"
SEISMIC_WEBSITE   = "https://www.seismicmaps.org/"

# =========================
# BROWSER SETTINGS
# =========================

HEADLESS = False  # True = run in background, False = show browser

YEAR_FOLDER_SUFFIX = "-XXX"