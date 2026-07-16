import os
import sys
import subprocess
import threading
import queue
import json

# --- SAX path bootstrap: make _shared importable (config, monday_config, project_log) ---
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_shared"))

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QGridLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QProgressBar, QDialog, QFrame,
    QComboBox, QCompleter, QLayout, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer, QRect, QSize, QPoint
from PySide6.QtGui import QFont, QIntValidator


# =========================
# FLOW LAYOUT — wraps items left-to-right like words on a page
# =========================

class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=8):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._items = []

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect, test_only):
        x = rect.x()
        y = rect.y()
        line_height = 0
        spacing = self.spacing()
        for item in self._items:
            w = item.sizeHint().width()
            h = item.sizeHint().height()
            next_x = x + w + spacing
            if next_x - spacing > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + spacing
                next_x = x + w + spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = next_x
            line_height = max(line_height, h)
        return y + line_height - rect.y()

# =========================
# COLORS
# =========================

BG          = "#1E1E2E"
PANEL       = "#2A2A3E"
BORDER      = "#3A3A5C"
BLUE        = "#4A90D9"
GREEN       = "#2ECC71"
RED         = "#E74C3C"
YELLOW      = "#F39C12"
TEXT        = "#E0E0F0"
SUBTEXT     = "#888AAA"
BTN_DEFAULT = "#2E3250"
BTN_HOVER   = "#3A4070"
DIALOG_BG   = "#252535"

BUTTON_BASE = f"""
    QPushButton {{
        background-color: {BTN_DEFAULT}; color: {TEXT};
        border: 1px solid {BORDER}; border-radius: 6px;
        padding: 8px 14px; font-family: Arial;
        font-size: 12px; text-align: left;
    }}
    QPushButton:hover {{ background-color: {BTN_HOVER}; border-color: {BLUE}; }}
    QPushButton:disabled {{ color: #555577; background-color: {PANEL}; border-color: #333355; }}
"""
BUTTON_GREEN = f"""
    QPushButton {{
        background-color: #1A4A2E; color: {GREEN};
        border: 1px solid {GREEN}; border-radius: 6px;
        padding: 8px 14px; font-family: Arial; font-size: 12px; text-align: left;
    }}
    QPushButton:hover {{ background-color: #1F5A36; }}
"""
BUTTON_RED_STYLE = f"""
    QPushButton {{
        background-color: #4A1A1A; color: {RED};
        border: 1px solid {RED}; border-radius: 6px;
        padding: 8px 14px; font-family: Arial; font-size: 12px; text-align: left;
    }}
    QPushButton:hover {{ background-color: #5A2020; }}
"""
BUTTON_DISABLED_STYLE = f"""
    QPushButton {{
        background-color: {PANEL}; color: #555577;
        border: 1px solid #333355; border-radius: 6px;
        padding: 8px 14px; font-family: Arial; font-size: 12px; text-align: left;
    }}
"""
DIALOG_BTN_BLUE = f"""
    QPushButton {{
        background-color: {BLUE}; color: white; border: none;
        border-radius: 6px; padding: 10px 24px;
        font-family: Arial; font-size: 13px; font-weight: bold; min-width: 80px;
    }}
    QPushButton:hover {{ background-color: #5AA0E9; }}
"""
DIALOG_BTN_GREEN = f"""
    QPushButton {{
        background-color: {GREEN}; color: white; border: none;
        border-radius: 6px; padding: 10px 24px;
        font-family: Arial; font-size: 13px; font-weight: bold; min-width: 80px;
    }}
    QPushButton:hover {{ background-color: #27AE60; }}
"""
DIALOG_BTN_RED = f"""
    QPushButton {{
        background-color: {RED}; color: white; border: none;
        border-radius: 6px; padding: 10px 24px;
        font-family: Arial; font-size: 13px; font-weight: bold; min-width: 80px;
    }}
    QPushButton:hover {{ background-color: #C0392B; }}
"""
DIALOG_BTN_GRAY = f"""
    QPushButton {{
        background-color: {BTN_DEFAULT}; color: {TEXT};
        border: 1px solid {BORDER}; border-radius: 6px;
        padding: 10px 24px; font-family: Arial; font-size: 13px; min-width: 80px;
    }}
    QPushButton:hover {{ background-color: {BTN_HOVER}; }}
"""

# =========================
# SETTINGS
# =========================

base_folder = (
    r"C:\Users\saxon\Dropbox\SHEAR FORCE"
    r"\1) CURRENT PROJECTS"
)
script_folder = os.path.dirname(os.path.abspath(__file__))
# --- SAX layout (added by migrate_to_sax) ---
SAX_ROOT    = os.path.dirname(script_folder)
SHARED_DIR  = os.path.join(SAX_ROOT, '_shared')
SCRIPTS_DIR = os.path.join(SAX_ROOT, 'calcs')
# --- end SAX layout ---

SCRIPTS = {
    "info":         "01_info.py",
    "monday":       "02_monday_contract.py",
    "apn":          "03_apn.py",
    "tot":          "04_tot.py",
    "asce":         "05_asce.py",
    "lat":          "06_lat.py",
    "vert":         "07_vert.py",
    "sync":         "08_sync.py",
    "notify":       "09_notify.py",
    "tot_location": "tot/tot_location.py",
    "tot_seismic":  "tot/tot_seismic.py",
    "tot_lat":      "tot/tot_lat.py",
    "tot_vert":     "tot/tot_vert.py",
    "tot_sync":     "tot_sync.py",
    "tot_notify":   "tot_notify.py",
}

NORMAL_STAGES  = ["apn", "tot", "asce", "lat", "vert"]
TOT_STAGES     = ["apn", "tot", "tot_location", "tot_seismic", "tot_lat", "tot_vert"]
DEFAULT_STAGES = NORMAL_STAGES

STAGE_LABELS = {
    "info":       "Project Info",
    "monday":     "Upload Contract + Location",
    "apn":        "APN Verification",
    "tot":        "TOT Verification",
    "asce":       "ASCE Hazard Data",
    "lat":        "Lateral Calcs",
    "vert":       "Vertical Calcs",
    "sync":       "07 — Sync",
    "notify":     "08 — Notify",
    "tot_location": "TOT Location Map",
    "tot_seismic":  "TOT Seismic Data",
    "tot_lat":      "TOT Lateral Calcs",
    "tot_vert":     "TOT Vertical Calcs",
    "tot_sync":    "08 — TOT Sync",
    "tot_notify": "08 — TOT Notify",
}

DEPENDENCIES = {
    "apn":      ["info"],
    "tot":      ["info", "apn"],
    "asce":     ["info", "apn", "tot"],
    "lat":      ["info", "apn", "tot", "asce"],
    "vert":     ["info", "apn", "tot", "asce", "lat"],
    "tot_location": ["info"],
    "tot_seismic":  ["info"],
    "tot_lat":      ["info", "tot_location", "tot_seismic"],
    "tot_vert":     ["info", "tot_lat"],
    "monday":   ["info"],
    "sync": [], "notify": [], "tot_sync": [], "tot_notify": [],
}

COMING_SOON = ["sync", "notify", "tot_sync", "tot_notify"]

SCRIPT_STEPS = {
    "info":     ["Checking INFO files", "Finding contract PDF",
                 "Reading PDF", "Extracting address",
                 "Extracting APN", "Extracting client info",
                 "Writing INFO file"],
    "monday":   ["Finding contract PDF", "Connecting to Monday",
                 "Finding board", "Finding project item", "Uploading file",
                 "Setting location"],
    "apn":      ["Reading INFO file", "Checking APN",
                 "Verifying APN", "Updating INFO file"],
    "tot":      ["Reading INFO file", "Opening TOT website",
                 "Searching address", "Detecting TOT status",
                 "Confirming status", "Updating INFO file"],
    "asce":     ["Reading INFO file", "Opening ASCE website",
                 "Entering address", "Selecting criteria",
                 "Downloading report", "Saving PDF"],
    "lat":      ["Reading INFO file", "Finding ASCE PDF",
                 "Copying template", "Extracting seismic values",
                 "Extracting wind values", "Writing Excel"],
    "vert":     ["Reading INFO file", "Finding LAT file",
                 "Copying template", "Copying cover data",
                 "Writing snow load", "Saving Excel"],
    "tot_location": ["Reading INFO file", "Opening Google Maps",
                     "Searching address", "Switching to satellite",
                     "Taking screenshot", "Updating INFO file"],
    "tot_seismic":  ["Reading INFO file", "Opening seismic website",
                     "Selecting ASCE 7-16", "Entering address",
                     "Waiting for PDF save", "Extracting seismic values",
                     "Updating INFO file"],
    "tot_lat":      ["Reading INFO file", "Copying TOT LAT template",
                     "Writing cover data", "Inserting screenshots",
                     "Writing seismic values", "Saving Excel"],
    "tot_vert":     ["Reading INFO file", "Finding TOT LAT file",
                     "Copying TOT VERT template", "Copying cover data",
                     "Writing snow load", "Saving Excel"],
}

# =========================
# SIGNALS
# =========================

class Signals(QObject):
    log               = Signal(str)
    stage_done        = Signal(str, bool)
    stage_warning     = Signal(str)
    pipeline_progress = Signal(int, int)
    stage_progress    = Signal(int, int)
    after_info        = Signal(bool)
    reset_bars        = Signal()
    req_open_pdf      = Signal(str, str)
    req_bad_template  = Signal(str)
    req_confirm_apn   = Signal(str)
    req_confirm_tot   = Signal(str)
    req_addr_mismatch = Signal(str, str)
    req_monday_mismatch = Signal(str, str)
    req_info_exists   = Signal(str)
    req_upload_confirm  = Signal(str)   # file already on Monday — ask to re-upload
    req_xl_complete     = Signal(str)   # XL files done — pipe-delimited paths
    req_xl_select       = Signal(str)   # XL file selection — type|file1|file2|...
    req_tot_manual      = Signal(str)   # TOT inconclusive or unmatched — manual Y/N
    req_asce_exists     = Signal(str)   # ASCE PDF already found — skip or rerun
    req_seismic_exists  = Signal(str)   # Seismic PDF already found — skip or rerun
    req_seismic_manual  = Signal(str)   # seismic website open — wait for user to save PDF
    req_location_exists = Signal(str)   # location screenshot already exists
    refresh_done        = Signal()      # background project scan finished — repopulate dropdown
    run_finished        = Signal()      # a stage/chain run finished — re-enable UI on GUI thread
    req_workflow_update = Signal(str)    # TOT determined mid-run — rebuild stage buttons on GUI thread
    stage_start         = Signal(int, int)  # a stage began (idx, total) — advance pipeline fill


signals = Signals()

# =========================
# PROJECT CACHE
# =========================

CACHE_FILE = os.path.join(script_folder, "project_cache.json")

def load_cache():
    if not os.path.exists(CACHE_FILE):
        return []
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_cache(projects):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(projects, f, indent=2)
    except Exception:
        pass

def scan_new_projects():
    """
    Scan only the 26-XXX folder, and only for projects
    not already in the cache. Finds the highest 26-xxx
    number in cache and only checks beyond that.
    """
    existing    = load_cache()
    known_paths = {p["path"] for p in existing}

    # Find highest 26-xxx number already cached
    last_26 = 0
    for p in existing:
        num = p.get("number", "")
        if num.startswith("26-"):
            try:
                n = int(num.split("-")[1])
                if n > last_26:
                    last_26 = n
            except Exception:
                pass

    year_folder = os.path.join(base_folder, "26-XXX")
    new_entries = []

    if not os.path.exists(year_folder):
        return existing, []

    try:
        for folder in sorted(os.listdir(year_folder)):
            full = os.path.join(year_folder, folder)
            if not os.path.isdir(full):
                continue
            parts = folder.split(" ", 1)
            if not (len(parts) >= 1 and "-" in parts[0]):
                continue
            number = parts[0].strip()
            if not number.startswith("26-"):
                continue
            try:
                n = int(number.split("-")[1])
            except Exception:
                continue
            # Only add if beyond last cached and not already known
            if n > last_26 and full not in known_paths:
                name = parts[1].strip() if len(parts) > 1 else ""
                new_entries.append({
                    "number": number,
                    "name":   name,
                    "path":   full,
                    "folder": folder,
                })
    except Exception:
        pass

    return existing, new_entries

def get_project_list():
    """Load from cache instantly. Returns list of display strings."""
    projects = load_cache()
    return [
        f"{p['number']} — {p['name']}" if p.get('name') else p['number']
        for p in sorted(projects, key=lambda x: x['number'], reverse=True)
    ]

# =========================
# HELPERS
# =========================

def find_project(project_number):
    year_prefix = project_number[:2]
    year_folder = os.path.join(base_folder, f"{year_prefix}-XXX")
    if not os.path.exists(year_folder):
        return None, None
    for folder in os.listdir(year_folder):
        if folder.startswith(project_number):
            return os.path.join(year_folder, folder), folder
    return None, None

def get_info_data(project_root, project_number):
    ui_folder = os.path.join(project_root, "UI")
    if not os.path.exists(ui_folder):
        return {}
    latest_time = 0
    info_path   = ""
    for file in os.listdir(ui_folder):
        upper = file.upper()
        if file.endswith(".txt") and "INFO" in upper and project_number in upper:
            full_path = os.path.join(ui_folder, file)
            t = os.path.getmtime(full_path)
            if t > latest_time:
                latest_time = t
                info_path   = full_path
    if not info_path:
        return {}
    data = {}
    with open(info_path, "r", encoding="utf-8") as f:
        for line in f:
            if "=" in line:
                key, _, val = line.partition("=")
                data[key.strip()] = val.strip()
    return data

# =========================
# APN WIDGET
# =========================

class APNWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        box_style = f"""
            QLineEdit {{
                background-color: {BG}; color: {TEXT};
                border: 1px solid {BORDER}; border-radius: 4px;
                padding: 8px 4px; font-family: Courier New;
                font-size: 16px; font-weight: bold;
            }}
            QLineEdit:focus {{ border-color: {BLUE}; }}
        """
        self.b1 = QLineEdit()
        self.b2 = QLineEdit()
        self.b3 = QLineEdit()
        for box in [self.b1, self.b2, self.b3]:
            box.setMaxLength(3)
            box.setFixedWidth(72)
            box.setAlignment(Qt.AlignCenter)
            box.setStyleSheet(box_style)
            box.setValidator(QIntValidator(0, 999))
        d1 = QLabel("-")
        d2 = QLabel("-")
        for d in [d1, d2]:
            d.setStyleSheet(
                f"color:{SUBTEXT};font-size:18px;font-weight:bold;padding:0 6px;"
            )
        layout.addWidget(self.b1)
        layout.addWidget(d1)
        layout.addWidget(self.b2)
        layout.addWidget(d2)
        layout.addWidget(self.b3)
        layout.addStretch()
        self.b1.textChanged.connect(lambda t: self._advance(t, self.b2))
        self.b2.textChanged.connect(lambda t: self._advance(t, self.b3))
        self.b2.installEventFilter(self)
        self.b3.installEventFilter(self)

    def _advance(self, text, next_box):
        if len(text) == 3:
            next_box.setFocus()
            next_box.selectAll()

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Backspace:
            if obj == self.b2 and self.b2.text() == "":
                self.b1.setFocus()
                self.b1.setCursorPosition(len(self.b1.text()))
                return True
            if obj == self.b3 and self.b3.text() == "":
                self.b2.setFocus()
                self.b2.setCursorPosition(len(self.b2.text()))
                return True
        return super().eventFilter(obj, event)

    def get_apn(self):
        return f"{self.b1.text()}-{self.b2.text()}-{self.b3.text()}"

    def set_apn(self, apn):
        parts = apn.split("-")
        if len(parts) == 3:
            self.b1.setText(parts[0])
            self.b2.setText(parts[1])
            self.b3.setText(parts[2])

    def is_valid(self):
        return (
            len(self.b1.text()) == 3
            and len(self.b2.text()) == 3
            and len(self.b3.text()) in (2, 3)
        )

# =========================
# BASE DIALOG
# =========================

class SAXDialog(QDialog):
    def __init__(self, parent, title):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(520)
        self.setStyleSheet(
            f"QDialog{{background-color:{DIALOG_BG};color:{TEXT};}}"
            f"QLabel{{color:{TEXT};font-family:Arial;}}"
        )
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(28, 24, 28, 24)
        self.main_layout.setSpacing(14)

    def showEvent(self, event):
        super().showEvent(event)
        if self.parent():
            pr = self.parent().geometry()
            x = pr.x() + (pr.width() - self.width()) // 2
            y = pr.y() + (pr.height() - self.height()) // 2
            self.move(x, y)

    def _title_label(self, text):
        lbl = QLabel(text)
        lbl.setFont(QFont("Arial", 13, QFont.Bold))
        lbl.setStyleSheet(f"color:{BLUE};")
        lbl.setWordWrap(True)
        return lbl

    def _body_label(self, text):
        lbl = QLabel(text)
        lbl.setFont(QFont("Arial", 10))
        lbl.setStyleSheet(f"color:{SUBTEXT};")
        lbl.setWordWrap(True)
        return lbl

    @staticmethod
    def _file_meta(filepath):
        """Return (date_str, size_str) for a file path."""
        import os
        from datetime import datetime
        try:
            t    = os.path.getmtime(filepath)
            date = datetime.fromtimestamp(t).strftime("%m/%d/%y  %I:%M %p")
            size = os.path.getsize(filepath)
            if size > 1024 * 1024:
                size_str = f"{size / 1024 / 1024:.1f} MB"
            else:
                size_str = f"{size / 1024:.1f} KB"
            return date, size_str
        except:
            return "", ""

    def _info_box(self, label, value):
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame{{background-color:{BTN_DEFAULT};"
            f"border:1px solid {BORDER};border-radius:6px;}}"
        )
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(14, 10, 14, 10)
        fl.setSpacing(2)
        lbl = QLabel(label)
        lbl.setFont(QFont("Arial", 8, QFont.Bold))
        lbl.setStyleSheet(
            f"color:{SUBTEXT};letter-spacing:1px;"
            f"background:transparent;border:none;"
        )
        val = QLabel(value)
        val.setFont(QFont("Arial", 11, QFont.Bold))
        val.setStyleSheet(
            f"color:{TEXT};background:transparent;border:none;"
        )
        val.setWordWrap(True)
        fl.addWidget(lbl)
        fl.addWidget(val)
        return frame

# =========================
# DIALOGS
# =========================

class ConfirmProjectDialog(SAXDialog):
    def __init__(self, parent, project_name):
        super().__init__(parent, "Confirm Project")
        self.main_layout.addWidget(
            self._title_label("Is this the correct project?")
        )
        self.main_layout.addWidget(
            self._info_box("PROJECT FOUND", project_name)
        )
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch()
        no_btn = QPushButton("NO — GO BACK")
        no_btn.setStyleSheet(DIALOG_BTN_GRAY)
        no_btn.clicked.connect(self.reject)
        yes_btn = QPushButton("YES — RUN INFO")
        yes_btn.setStyleSheet(DIALOG_BTN_BLUE)
        yes_btn.clicked.connect(self.accept)
        yes_btn.setDefault(True)
        row.addWidget(no_btn)
        row.addWidget(yes_btn)
        self.main_layout.addLayout(row)


class OpenPDFDialog(SAXDialog):
    def __init__(self, parent, pdf_name):
        super().__init__(parent, "Contract PDF Found")
        self.main_layout.addWidget(
            self._title_label("Contract PDF found.")
        )
        self.main_layout.addWidget(
            self._info_box("PDF FILE", pdf_name)
        )
        self.main_layout.addWidget(
            self._body_label("Would you like to open it for review?")
        )
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch()
        no_btn = QPushButton("NO — CONTINUE")
        no_btn.setStyleSheet(DIALOG_BTN_GRAY)
        no_btn.clicked.connect(self.reject)
        yes_btn = QPushButton("YES — OPEN PDF")
        yes_btn.setStyleSheet(DIALOG_BTN_BLUE)
        yes_btn.clicked.connect(self.accept)
        yes_btn.setDefault(True)
        row.addWidget(no_btn)
        row.addWidget(yes_btn)
        self.main_layout.addLayout(row)


class InfoExistsDialog(SAXDialog):
    def __init__(self, parent, files):
        super().__init__(parent, "INFO File Already Exists")
        from datetime import datetime

        self.files         = files
        self.selected_file = None
        self._row_widgets  = []

        self.main_layout.addWidget(
            self._title_label(f"{len(files)} INFO file(s) found for this project.")
        )
        self.main_layout.addWidget(
            self._body_label("What would you like to do?")
        )

        for f in files:
            try:
                modified = os.path.getmtime(f)
                date_str = datetime.fromtimestamp(modified).strftime("%m/%d/%y %I:%M %p")
            except:
                date_str = ""

            file_box = self._info_box("FILE", f"{os.path.basename(f)}  —  {date_str}")
            file_box.setCursor(Qt.PointingHandCursor)
            file_box.mousePressEvent = lambda e, fp=f, w=file_box: self._select_file(fp, w)
            self.main_layout.addWidget(file_box)
            self._row_widgets.append((f, file_box))

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addStretch()
        skip_btn = QPushButton("SKIP — USE EXISTING")
        skip_btn.setStyleSheet(DIALOG_BTN_BLUE)
        skip_btn.clicked.connect(lambda: self.done(3))
        self.overwrite_btn = QPushButton("OVERWRITE EXISTING")
        self.overwrite_btn.setStyleSheet(DIALOG_BTN_RED)
        self.overwrite_btn.clicked.connect(lambda: self.done(2))
        new_btn = QPushButton("RE-RUN — CREATE NEW")
        new_btn.setStyleSheet(DIALOG_BTN_GREEN)
        new_btn.clicked.connect(self.accept)
        new_btn.setDefault(True)
        row.addWidget(skip_btn)
        row.addWidget(self.overwrite_btn)
        row.addWidget(new_btn)
        self.main_layout.addLayout(row)

    def _select_file(self, filepath, widget):
        # Reset all
        for f, w in self._row_widgets:
            w.setStyleSheet(w.styleSheet().replace(
                f"border:2px solid {BLUE}", f"border:1px solid {BORDER}"
            ))
        # Highlight selected with blue border
        current = widget.styleSheet()
        widget.setStyleSheet(current.replace(
            f"border:1px solid {BORDER}", f"border:2px solid {BLUE}"
        ))
        self.selected_file = filepath


class ManualAddressDialog(SAXDialog):
    def __init__(self, parent):
        super().__init__(parent, "Manual Address Entry")
        self.result_address = ""
        self.main_layout.addWidget(
            self._title_label("Address extraction failed.")
        )
        self.main_layout.addWidget(
            self._body_label(
                "The PDF has been opened. "
                "Please type the project address below."
            )
        )
        addr_lbl = QLabel("PROJECT ADDRESS")
        addr_lbl.setFont(QFont("Arial", 9, QFont.Bold))
        addr_lbl.setStyleSheet(f"color:{SUBTEXT};letter-spacing:1px;")
        self.main_layout.addWidget(addr_lbl)
        self.address_input = QLineEdit()
        self.address_input.setPlaceholderText(
            "e.g. 123 Main St, Truckee, CA 96161"
        )
        self.address_input.setStyleSheet(
            f"QLineEdit{{background-color:{BG};color:{TEXT};"
            f"border:1px solid {BORDER};border-radius:6px;"
            f"padding:10px 12px;font-family:Arial;font-size:13px;}}"
            f"QLineEdit:focus{{border-color:{BLUE};}}"
        )
        self.main_layout.addWidget(self.address_input)
        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"color:{RED};font-size:11px;")
        self.main_layout.addWidget(self.error_label)
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch()
        cancel_btn = QPushButton("CANCEL")
        cancel_btn.setStyleSheet(DIALOG_BTN_GRAY)
        cancel_btn.clicked.connect(self.reject)
        confirm_btn = QPushButton("CONFIRM ADDRESS")
        confirm_btn.setStyleSheet(DIALOG_BTN_BLUE)
        confirm_btn.clicked.connect(self._confirm)
        confirm_btn.setDefault(True)
        row.addWidget(cancel_btn)
        row.addWidget(confirm_btn)
        self.main_layout.addLayout(row)

    def _confirm(self):
        addr = self.address_input.text().strip()
        if not addr:
            self.error_label.setText("Please enter an address.")
            return
        self.result_address = addr
        self.accept()


class APNDialog(SAXDialog):
    def __init__(self, parent, current_apn, contract_pdf="", padded=False):
        super().__init__(parent, "Verify APN")
        self._contract_pdf = contract_pdf
        self.result_apn = current_apn

        if padded:
            self.main_layout.addWidget(
                self._title_label("APN has 8 digits — please verify.")
            )
            self.main_layout.addWidget(
                self._body_label(
                    "Enter the correct APN below and confirm."
                )
            )
        else:
            self.main_layout.addWidget(self._title_label("Verify the APN."))
            self.main_layout.addWidget(
                self._body_label(
                    "If correct, click Confirm. "
                    "If not, edit the boxes below."
                )
            )

        self.main_layout.addWidget(
            self._info_box("APN FROM CONTRACT", current_apn)
        )
        apn_lbl = QLabel("APN")
        apn_lbl.setFont(QFont("Arial", 9, QFont.Bold))
        apn_lbl.setStyleSheet(f"color:{SUBTEXT};letter-spacing:1px;")
        self.main_layout.addWidget(apn_lbl)
        self.apn_widget = APNWidget()
        self.apn_widget.set_apn(current_apn)
        self.main_layout.addWidget(self.apn_widget)
        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"color:{RED};font-size:11px;")
        self.main_layout.addWidget(self.error_label)
        open_btn = QPushButton("OPEN CONTRACT PDF")
        open_btn.setStyleSheet(DIALOG_BTN_GRAY)
        open_btn.clicked.connect(self._open_pdf)
        self.main_layout.addWidget(open_btn)
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch()
        cancel_btn = QPushButton("CANCEL")
        cancel_btn.setStyleSheet(DIALOG_BTN_GRAY)
        cancel_btn.clicked.connect(self.reject)
        confirm_btn = QPushButton("CONFIRM APN")
        confirm_btn.setStyleSheet(DIALOG_BTN_BLUE)
        confirm_btn.clicked.connect(self._confirm)
        confirm_btn.setDefault(True)
        row.addWidget(cancel_btn)
        row.addWidget(confirm_btn)
        self.main_layout.addLayout(row)

    def _open_pdf(self):
        if self._contract_pdf and os.path.exists(self._contract_pdf):
            os.startfile(self._contract_pdf)
        else:
            self.error_label.setText("Contract PDF not found.")

    def _confirm(self):
        if not self.apn_widget.is_valid():
            self.error_label.setText(
                "APN must be XXX-XXX-XX or XXX-XXX-XXX."
            )
            return
        self.result_apn = self.apn_widget.get_apn()
        self.accept()


class AddressMismatchDialog(SAXDialog):
    def __init__(self, parent, info_address, found_address):
        super().__init__(parent, "Address Mismatch")
        self.main_layout.addWidget(
            self._title_label("Address mismatch detected.")
        )
        self.main_layout.addWidget(
            self._body_label(
                "The TOT website found a different address. "
                "Update the verified project address?"
            )
        )
        self.main_layout.addWidget(
            self._info_box("INFO FILE ADDRESS", info_address)
        )
        self.main_layout.addWidget(
            self._info_box("TOT WEBSITE ADDRESS", found_address)
        )
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch()
        no_btn = QPushButton("NO — KEEP EXISTING")
        no_btn.setStyleSheet(DIALOG_BTN_GRAY)
        no_btn.clicked.connect(self.reject)
        yes_btn = QPushButton("YES — UPDATE")
        yes_btn.setStyleSheet(DIALOG_BTN_BLUE)
        yes_btn.clicked.connect(self.accept)
        yes_btn.setDefault(True)
        row.addWidget(no_btn)
        row.addWidget(yes_btn)
        self.main_layout.addLayout(row)


class TOTConfirmDialog(SAXDialog):
    def __init__(self, parent, tot_status):
        super().__init__(parent, "Confirm TOT Status")
        status_text = (
            "TOT (Town of Truckee)" if tot_status == "Y" else "NOT TOT"
        )
        self.main_layout.addWidget(
            self._title_label("Is this TOT status correct?")
        )
        self.main_layout.addWidget(
            self._info_box("DETECTED TOT STATUS", status_text)
        )
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch()
        override_btn = QPushButton("OVERWRITE EXISTING")
        override_btn.setStyleSheet(DIALOG_BTN_RED)
        override_btn.clicked.connect(lambda: self.done(2))
        confirm_btn = QPushButton("CONFIRM")
        confirm_btn.setStyleSheet(DIALOG_BTN_BLUE)
        confirm_btn.clicked.connect(self.accept)
        confirm_btn.setDefault(True)
        row.addWidget(override_btn)
        row.addWidget(confirm_btn)
        self.main_layout.addLayout(row)


class UploadConfirmDialog(SAXDialog):
    """Shown only when the file already exists on Monday — ask to re-upload."""
    def __init__(self, parent, contract_name, contract_path=""):
        super().__init__(parent, "File Already on Monday")
        self.main_layout.addWidget(
            self._title_label("This file already exists on Monday.com.")
        )
        self.main_layout.addWidget(
            self._info_box("CONTRACT FILE", os.path.basename(contract_name))
        )
        if contract_path:
            date_str, _ = self._file_meta(contract_path)
            if date_str:
                self.main_layout.addWidget(self._info_box("DATE", date_str))
        self.main_layout.addWidget(
            self._body_label(
                "The contract was already found on Monday. "
                "Upload it again anyway?"
            )
        )
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch()
        skip_btn = QPushButton("SKIP — USE EXISTING")
        skip_btn.setStyleSheet(DIALOG_BTN_BLUE)
        skip_btn.clicked.connect(lambda: self.done(2))
        upload_btn = QPushButton("RE-RUN — UPLOAD AGAIN")
        upload_btn.setStyleSheet(DIALOG_BTN_GREEN)
        upload_btn.clicked.connect(self.accept)
        upload_btn.setDefault(True)
        row.addWidget(skip_btn)
        row.addWidget(upload_btn)
        self.main_layout.addLayout(row)


class MondayMismatchDialog(SAXDialog):
    def __init__(self, parent, monday_name, local_name):
        super().__init__(parent, "Monday Item Mismatch")
        self.main_layout.addWidget(
            self._title_label("Monday item name does not match.")
        )
        self.main_layout.addWidget(
            self._info_box("MONDAY ITEM", monday_name)
        )
        self.main_layout.addWidget(
            self._info_box("LOCAL FOLDER", local_name)
        )
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch()
        no_btn = QPushButton("NO — CANCEL")
        no_btn.setStyleSheet(DIALOG_BTN_GRAY)
        no_btn.clicked.connect(self.reject)
        yes_btn = QPushButton("YES — USE THIS")
        yes_btn.setStyleSheet(DIALOG_BTN_BLUE)
        yes_btn.clicked.connect(self.accept)
        yes_btn.setDefault(True)
        row.addWidget(no_btn)
        row.addWidget(yes_btn)
        self.main_layout.addLayout(row)


class DependencyDialog(SAXDialog):
    def __init__(self, parent, stage_label, missing_label):
        super().__init__(parent, "Stage Dependency")
        self.main_layout.addWidget(
            self._title_label(f'"{missing_label}" must run first.')
        )
        self.main_layout.addWidget(
            self._body_label(
                f'To run "{stage_label}", "{missing_label}" must '
                f'complete first.\n\nRun "{missing_label}" now and '
                f'then continue to "{stage_label}"?'
            )
        )
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch()
        cancel_btn = QPushButton("CANCEL")
        cancel_btn.setStyleSheet(DIALOG_BTN_GRAY)
        cancel_btn.clicked.connect(self.reject)
        run_btn = QPushButton(f"Run {missing_label} First")
        run_btn.setStyleSheet(DIALOG_BTN_BLUE)
        run_btn.clicked.connect(self.accept)
        run_btn.setDefault(True)
        row.addWidget(cancel_btn)
        row.addWidget(run_btn)
        self.main_layout.addLayout(row)


# =========================
# LOCATION EXISTS DIALOG
# =========================

class LocationExistsDialog(SAXDialog):
    def __init__(self, parent, path):
        super().__init__(parent, "Location Screenshot Exists")
        self.main_layout.addWidget(self._title_label("Location screenshot already exists."))
        date_str, _ = self._file_meta(path)
        self.main_layout.addWidget(self._info_box("FILE", os.path.basename(path)))
        self.main_layout.addWidget(self._info_box("DATE", date_str))
        self.main_layout.addWidget(self._body_label("Skip and use existing, or re-run?"))
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch()
        skip_btn = QPushButton("SKIP — USE EXISTING")
        skip_btn.setStyleSheet(DIALOG_BTN_BLUE)
        skip_btn.clicked.connect(lambda: self.done(2))
        rerun_btn = QPushButton("RE-RUN — CREATE NEW")
        rerun_btn.setStyleSheet(DIALOG_BTN_GREEN)
        rerun_btn.clicked.connect(self.accept)
        rerun_btn.setDefault(True)
        row.addWidget(skip_btn)
        row.addWidget(rerun_btn)
        self.main_layout.addLayout(row)


# =========================
# SEISMIC EXISTS DIALOG
# =========================

class SeismicExistsDialog(SAXDialog):
    def __init__(self, parent, filename, date_str):
        super().__init__(parent, "Seismic Report Already Exists")
        self.main_layout.addWidget(
            self._title_label("Seismic report already found.")
        )
        self.main_layout.addWidget(self._info_box("FILE", filename))
        self.main_layout.addWidget(self._info_box("DATE", date_str))
        self.main_layout.addWidget(
            self._body_label("Use existing file or re-run seismic report?")
        )
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch()
        skip_btn = QPushButton("SKIP — USE EXISTING")
        skip_btn.setStyleSheet(DIALOG_BTN_BLUE)
        skip_btn.clicked.connect(lambda: self.done(2))
        rerun_btn = QPushButton("RE-RUN — CREATE NEW")
        rerun_btn.setStyleSheet(DIALOG_BTN_GREEN)
        rerun_btn.clicked.connect(self.accept)
        rerun_btn.setDefault(True)
        row.addWidget(skip_btn)
        row.addWidget(rerun_btn)
        self.main_layout.addLayout(row)


# =========================
# SEISMIC MANUAL DIALOG
# =========================

class SeismicManualDialog(SAXDialog):
    def __init__(self, parent, pdf_path):
        super().__init__(parent, "Save Seismic PDF")
        self.main_layout.addWidget(
            self._title_label("Seismic website is open.")
        )
        self.main_layout.addWidget(
            self._body_label(
                "Please search for the project, select ASCE 7-16, "
                "and print/save the PDF to your CALCULATIONS folder. "
                "Click Done when the PDF has been saved."
            )
        )
        self.main_layout.addWidget(
            self._info_box("SAVE PDF TO", pdf_path)
        )
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch()
        skip_btn = QPushButton("SKIP — USE EXISTING")
        skip_btn.setStyleSheet(DIALOG_BTN_GRAY)
        skip_btn.clicked.connect(lambda: self.done(2))
        done_btn = QPushButton("DONE — PDF SAVED")
        done_btn.setStyleSheet(DIALOG_BTN_GREEN)
        done_btn.clicked.connect(self.accept)
        done_btn.setDefault(True)
        row.addWidget(skip_btn)
        row.addWidget(done_btn)
        self.main_layout.addLayout(row)


# =========================
# ASCE EXISTS DIALOG
# =========================

class ASCEExistsDialog(SAXDialog):
    def __init__(self, parent, filename):
        super().__init__(parent, "ASCE Report Already Exists")
        self.main_layout.addWidget(
            self._title_label("ASCE report already found.")
        )
        date_str, _ = self._file_meta(filename)
        self.main_layout.addWidget(self._info_box("FILE", os.path.basename(filename)))
        self.main_layout.addWidget(self._info_box("DATE", date_str))
        self.main_layout.addWidget(
            self._body_label("Skip and use existing, or re-run?")
        )
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch()
        skip_btn = QPushButton("SKIP — USE EXISTING")
        skip_btn.setStyleSheet(DIALOG_BTN_BLUE)
        skip_btn.clicked.connect(lambda: self.done(2))
        rerun_btn = QPushButton("RE-RUN — CREATE NEW")
        rerun_btn.setStyleSheet(DIALOG_BTN_GREEN)
        rerun_btn.clicked.connect(self.accept)
        rerun_btn.setDefault(True)
        row.addWidget(skip_btn)
        row.addWidget(rerun_btn)
        self.main_layout.addLayout(row)


# =========================
# TOT MANUAL DIALOG
# =========================

class TOTManualDialog(SAXDialog):
    def __init__(self, parent, payload):
        super().__init__(parent, "TOT Manual Override")
        # payload format: "message|address|apn"
        parts   = payload.split("|")
        message = parts[0].strip()
        address = parts[1].strip() if len(parts) > 1 else ""
        apn     = parts[2].strip() if len(parts) > 2 else ""

        self.main_layout.addWidget(
            self._title_label("Manual Override Required")
        )
        self.main_layout.addWidget(self._body_label(message))

        if address:
            self.main_layout.addWidget(
                self._info_box("PROJECT ADDRESS", address)
            )
        if apn:
            self.main_layout.addWidget(
                self._info_box("VERIFIED APN", apn)
            )

        self.main_layout.addWidget(
            self._body_label("Is this a TOT project?")
        )
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch()
        no_btn = QPushButton("NO — NOT TOT")
        no_btn.setStyleSheet(DIALOG_BTN_BLUE)
        no_btn.clicked.connect(self.reject)
        yes_btn = QPushButton("YES — TOT PROJECT")
        yes_btn.setStyleSheet(DIALOG_BTN_GREEN)
        yes_btn.clicked.connect(self.accept)
        yes_btn.setDefault(True)
        row.addWidget(no_btn)
        row.addWidget(yes_btn)
        self.main_layout.addLayout(row)



# =========================
# XL FILE SELECT DIALOG
# =========================

class XLSelectDialog(SAXDialog):
    """Select existing XL file to update, or create new from template."""
    def __init__(self, parent, files, file_type="XL"):
        super().__init__(parent, f"{file_type} File Found")
        from datetime import datetime

        self.files         = files
        self.selected_file = None
        self._row_widgets  = []

        self.main_layout.addWidget(
            self._title_label(f"{len(files)} existing {file_type} file(s) found.")
        )
        self.main_layout.addWidget(
            self._body_label("Select a file to update, or create new from template.")
        )

        for f in files:
            try:
                modified = os.path.getmtime(f)
                date_str = datetime.fromtimestamp(modified).strftime("%m/%d/%y %I:%M %p")
            except:
                date_str = ""

            file_box = self._info_box(
                "FILE", f"{os.path.basename(f)}  —  {date_str}"
            )
            file_box.setCursor(Qt.PointingHandCursor)
            file_box.mousePressEvent = lambda e, fp=f, w=file_box: self._select(fp, w)
            self.main_layout.addWidget(file_box)
            self._row_widgets.append((f, file_box))

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addStretch()

        self.update_btn = QPushButton("UPDATE SELECTED")
        self.update_btn.setStyleSheet(DIALOG_BTN_BLUE)
        self.update_btn.setEnabled(False)
        self.update_btn.clicked.connect(lambda: self.done(2))

        new_btn = QPushButton("CREATE NEW FROM TEMPLATE")
        new_btn.setStyleSheet(DIALOG_BTN_GREEN)
        new_btn.clicked.connect(self.accept)
        new_btn.setDefault(True)

        row.addWidget(self.update_btn)
        row.addWidget(new_btn)
        self.main_layout.addLayout(row)

    def _select(self, filepath, widget):
        for f, w in self._row_widgets:
            w.setStyleSheet(w.styleSheet().replace(
                f"border:2px solid {BLUE}", f"border:1px solid {BORDER}"
            ))
        widget.setStyleSheet(widget.styleSheet().replace(
            f"border:1px solid {BORDER}", f"border:2px solid {BLUE}"
        ))
        self.selected_file = filepath
        self.update_btn.setEnabled(True)
        self.update_btn.setText(f"UPDATE SELECTED")


# =========================
# XL COMPLETE DIALOG
# =========================

class XLCompleteDialog(SAXDialog):
    def __init__(self, parent, paths, headless=False):
        super().__init__(parent, "XL Files Created")
        self.paths     = paths
        self.keep_open = []

        self.main_layout.addWidget(
            self._title_label("XL files created successfully.")
        )

        if headless:
            self.main_layout.addWidget(
                self._body_label("Files were created in the background. Open for review?")
            )
        else:
            self.main_layout.addWidget(
                self._body_label("Leave open for review?")
            )

        from PySide6.QtWidgets import QCheckBox
        self.checkboxes = []
        for path in paths:
            cb = QCheckBox(os.path.basename(path))
            cb.setStyleSheet(
                f"QCheckBox{{color:{TEXT};font-family:Arial;font-size:12px;}}"
                f"QCheckBox::indicator{{width:16px;height:16px;}}"
                f"QCheckBox::indicator:unchecked{{border:1px solid {BORDER};"
                f"border-radius:3px;background:{BTN_DEFAULT};}}"
                f"QCheckBox::indicator:checked{{border:1px solid {GREEN};"
                f"border-radius:3px;background:{GREEN};}}"
            )
            cb.setChecked(True)
            cb.stateChanged.connect(self._update_yes_btn)
            self.main_layout.addWidget(cb)
            self.checkboxes.append(cb)

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch()

        self.no_btn = QPushButton("NO — CLOSE")
        self.no_btn.setStyleSheet(DIALOG_BTN_RED)
        self.no_btn.clicked.connect(self.reject)

        yes_text = "YES — OPEN" if headless else "YES — LEAVE OPEN"
        self.yes_btn = QPushButton(yes_text)
        self.yes_btn.setStyleSheet(DIALOG_BTN_GREEN)
        self.yes_btn.clicked.connect(self._confirm)
        self.yes_btn.setDefault(True)

        row.addWidget(self.no_btn)
        row.addWidget(self.yes_btn)
        self.main_layout.addLayout(row)
        self._update_yes_btn()

    def _update_yes_btn(self):
        any_checked = any(cb.isChecked() for cb in self.checkboxes)
        self.yes_btn.setEnabled(any_checked)

    def _confirm(self):
        self.keep_open = [
            self.paths[i]
            for i, cb in enumerate(self.checkboxes)
            if cb.isChecked()
        ]
        self.accept()


# =========================
# SPLIT BUTTON
# =========================

class SplitButton(QWidget):
    run_clicked   = Signal()
    arrow_clicked = Signal()

    def __init__(self, label, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        run_style = (
            f"QPushButton{{background-color:{BLUE};color:white;border:none;"
            f"border-top-left-radius:8px;border-bottom-left-radius:8px;"
            f"border-top-right-radius:0px;border-bottom-right-radius:0px;"
            f"padding:11px 16px;font-family:Arial;font-size:13px;"
            f"font-weight:bold;text-align:left;}}"
            f"QPushButton:hover{{background-color:#5AA0E9;}}"
            f"QPushButton:disabled{{background-color:#2A2A3E;color:{SUBTEXT};}}"
        )
        arrow_style = (
            f"QPushButton{{background-color:#3A80C9;color:white;border:none;"
            f"border-top-left-radius:0px;border-bottom-left-radius:0px;"
            f"border-top-right-radius:8px;border-bottom-right-radius:8px;"
            f"padding:11px 10px;font-family:Arial;font-size:13px;"
            f"font-weight:bold;min-width:32px;max-width:32px;}}"
            f"QPushButton:hover{{background-color:#5AA0E9;}}"
            f"QPushButton:disabled{{background-color:#252535;color:{SUBTEXT};}}"
        )
        self.run_btn   = QPushButton(f"▶▶  {label}")
        self.arrow_btn = QPushButton("▼")
        self.run_btn.setMinimumHeight(34)
        self.arrow_btn.setMinimumHeight(34)
        self.arrow_btn.setFixedWidth(36)
        self.run_btn.setStyleSheet(run_style)
        self.arrow_btn.setStyleSheet(arrow_style)
        self.run_btn.clicked.connect(self.run_clicked)
        self.arrow_btn.clicked.connect(self._toggle_arrow)
        layout.addWidget(self.run_btn, 1)
        layout.addWidget(self.arrow_btn)
        self._expanded = False

    def _toggle_arrow(self):
        self._expanded = not self._expanded
        self.arrow_btn.setText("▲" if self._expanded else "▼")
        self.arrow_clicked.emit()

    def set_enabled(self, enabled):
        self.run_btn.setEnabled(enabled)
        self.arrow_btn.setEnabled(enabled)


# =========================
# STAGE BUTTON
# =========================

class StageButton(QPushButton):
    def __init__(self, key, parent=None):
        label = STAGE_LABELS.get(key, key)
        super().__init__(f"      ▶  {label}", parent)
        self.key = key
        self.setMinimumHeight(36)
        self.setCursor(Qt.PointingHandCursor)
        if key in COMING_SOON:
            self.setStyleSheet(BUTTON_DISABLED_STYLE)
            self.setEnabled(False)
            self.setText(f"      ⋯  {label}  (coming soon)")
        else:
            self.setStyleSheet(BUTTON_BASE)
            self.setEnabled(False)

    def set_enabled_active(self, enabled):
        if self.key not in COMING_SOON:
            self.setEnabled(enabled)

    def set_running(self):
        self.setText(f"      ⟳  {STAGE_LABELS.get(self.key, self.key)}")
        self.setStyleSheet(BUTTON_BASE)
        self.setEnabled(False)

    def set_success(self):
        self.setText(f"      ✔  {STAGE_LABELS.get(self.key, self.key)}")
        self.setStyleSheet(BUTTON_GREEN)
        self.setEnabled(True)

    def set_failed(self):
        self.setText(f"      ✖  {STAGE_LABELS.get(self.key, self.key)}")
        self.setStyleSheet(BUTTON_RED_STYLE)
        self.setEnabled(True)

    def reset(self):
        self.setText(f"      ▶  {STAGE_LABELS.get(self.key, self.key)}")
        self.setStyleSheet(BUTTON_BASE)


# =========================
# SCRIPT RUNNER
# Background thread emits signals → main thread shows
# dialogs → result put into queue → background reads queue.
# NOTHING continues automatically if dialog fails.
# =========================

class ScriptRunner(QObject):

    def __init__(self):
        super().__init__()
        self._proc              = None
        self._stopped           = False
        self._result_queue      = queue.Queue()
        self._xl_paths          = []
        self._current_stage_key = ""
        self._stage_had_warning = False

    def stop(self):
        self._stopped = True
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass

    def put_result(self, value):
        self._result_queue.put(value)

    def _wait_for_result(self, key, timeout=300):
        """
        Wait for dialog result. If timeout, stop everything.
        Never continues automatically.
        """
        # Clear any stale values from previous runs
        while not self._result_queue.empty():
            try:
                self._result_queue.get_nowait()
            except:
                break
        try:
            return self._result_queue.get(timeout=timeout)
        except Exception:
            signals.log.emit(
                "ERROR: Dialog timed out — pipeline stopped."
            )
            self._proc.terminate()
            signals.stage_done.emit(key, False)
            return None

    def run(self, key, project_number, force=False):
        self._stopped = False
        path = os.path.join(SCRIPTS_DIR, SCRIPTS.get(key, ""))

        if not os.path.exists(path):
            signals.log.emit(f"ERROR: Script not found: {path}")
            signals.stage_done.emit(key, False)
            return False

        steps      = SCRIPT_STEPS.get(key, [])
        total      = len(steps)
        step_index = [0]

        try:
            cmd = [sys.executable, "-u", path, project_number]
            if force:
                cmd.append("--force")
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1
            )
        except Exception as e:
            signals.log.emit(f"ERROR launching script: {e}")
            signals.stage_done.emit(key, False)
            return False

        for raw_line in self._proc.stdout:
            if self._stopped:
                break
            line = raw_line.rstrip()

            # ── STEP MARKER ──
            if line.startswith("UI_STEP:"):
                step_index[0] += 1
                signals.log.emit(
                    f"  ▸ {line.replace('UI_STEP:', '').strip()}"
                )
                if total > 0:
                    signals.stage_progress.emit(step_index[0], total)
                continue

            # ── INFO EXISTS ──
            if line.startswith("UI_INFO_EXISTS:"):
                files_str = line.replace("UI_INFO_EXISTS:", "").strip()
                signals.req_info_exists.emit(files_str)
                result = self._wait_for_result(key, timeout=300)
                if result is None:
                    return False
                self._proc.stdin.write(result + "\n")
                self._proc.stdin.flush()
                continue

            # ── OPEN PDF ──
            if line.startswith("UI_OPEN_PDF:"):
                pdf_path = line.replace("UI_OPEN_PDF:", "").strip()
                signals.req_open_pdf.emit(
                    pdf_path, os.path.basename(pdf_path)
                )
                self._wait_for_result(key, timeout=60)
                continue

            # ── BAD TEMPLATE ──
            if line.startswith("UI_BAD_TEMPLATE:"):
                pdf_path = line.replace("UI_BAD_TEMPLATE:", "").strip()
                signals.req_bad_template.emit(pdf_path)
                result = self._wait_for_result(key, timeout=300)
                if result is None:
                    return False
                self._proc.stdin.write(
                    (result or "CANCELLED") + "\n"
                )
                self._proc.stdin.flush()
                continue

            # ── CONFIRM APN ──
            if line.startswith("UI_CONFIRM_APN:"):
                signals.req_confirm_apn.emit(
                    line.replace("UI_CONFIRM_APN:", "").strip()
                )
                result = self._wait_for_result(key, timeout=300)
                if result is None:
                    return False
                self._proc.stdin.write(result + "\n")
                self._proc.stdin.flush()
                continue

            # ── CONFIRM TOT ──
            if line.startswith("UI_CONFIRM_TOT:"):
                signals.req_confirm_tot.emit(
                    line.replace("UI_CONFIRM_TOT:", "").strip()
                )
                result = self._wait_for_result(key, timeout=300)
                if result is None:
                    return False
                self._proc.stdin.write(result + "\n")
                self._proc.stdin.flush()
                continue

            # ── ADDRESS MISMATCH ──
            if line.startswith("UI_ADDRESS_MISMATCH:"):
                parts = line.replace(
                    "UI_ADDRESS_MISMATCH:", ""
                ).strip().split("|")
                signals.req_addr_mismatch.emit(
                    parts[0] if len(parts) > 0 else "",
                    parts[1] if len(parts) > 1 else ""
                )
                result = self._wait_for_result(key, timeout=300)
                if result is None:
                    return False
                self._proc.stdin.write(result + "\n")
                self._proc.stdin.flush()
                continue

            # ── LOCATION EXISTS — skip or rerun ──
            if line.startswith("UI_LOCATION_EXISTS:"):
                path = line.replace("UI_LOCATION_EXISTS:", "").strip()
                signals.req_location_exists.emit(path)
                result = self._wait_for_result(key, timeout=120)
                if result is None:
                    return False
                self._proc.stdin.write(result + "\n")
                self._proc.stdin.flush()
                continue

            # ── SEISMIC EXISTS — skip or rerun ──
            if line.startswith("UI_SEISMIC_EXISTS:"):
                payload = line.replace("UI_SEISMIC_EXISTS:", "").strip()
                signals.req_seismic_exists.emit(payload)
                result = self._wait_for_result(key, timeout=120)
                if result is None:
                    return False
                self._proc.stdin.write(result + "\n")
                self._proc.stdin.flush()
                continue

            # ── SEISMIC MANUAL — wait for user to save PDF ──
            if line.startswith("UI_SEISMIC_MANUAL:"):
                pdf_path = line.replace("UI_SEISMIC_MANUAL:", "").strip()
                signals.req_seismic_manual.emit(pdf_path)
                result = self._wait_for_result(key, timeout=600)
                if result is None:
                    return False
                self._proc.stdin.write(result + "\n")
                self._proc.stdin.flush()
                continue

            # ── ASCE EXISTS — ask skip or rerun ──
            if line.startswith("UI_ASCE_EXISTS:"):
                filename = line.replace("UI_ASCE_EXISTS:", "").strip()
                signals.req_asce_exists.emit(filename)
                result = self._wait_for_result(key, timeout=120)
                if result is None:
                    return False
                self._proc.stdin.write(result + "\n")
                self._proc.stdin.flush()
                continue

            # ── TOT MANUAL OVERRIDE ──
            if line.startswith("UI_TOT_MANUAL:"):
                msg = line.replace("UI_TOT_MANUAL:", "").strip()
                signals.req_tot_manual.emit(msg)
                result = self._wait_for_result(key, timeout=300)
                if result is None:
                    return False
                self._proc.stdin.write(result + "\n")
                self._proc.stdin.flush()
                continue

            # ── WARNING LOG — show in yellow in status log ──
            # ── XL FILE SELECT — update existing or create new ──
            if line.startswith("UI_XL_SELECT:"):
                payload = line.replace("UI_XL_SELECT:", "").strip()
                signals.req_xl_select.emit(payload)
                result = self._wait_for_result(key, timeout=300)
                if result is None:
                    return False
                self._proc.stdin.write(result + "\n")
                self._proc.stdin.flush()
                continue

            # ── WARNING with specific stage key ──
            if line.startswith("UI_LOG_WARNING_KEY:"):
                payload = line.replace("UI_LOG_WARNING_KEY:", "").strip()
                parts   = payload.split(":", 1)
                if len(parts) == 2:
                    warn_key, warn_msg = parts
                    signals.log.emit(f"WARNING: {warn_msg}")
                    signals.stage_warning.emit(warn_key.strip())
                continue

            if line.startswith("UI_LOG_WARNING:"):
                msg = line.replace("UI_LOG_WARNING:", "").strip()
                signals.log.emit(f"WARNING: {msg}")
                if self._current_stage_key:
                    self._stage_had_warning = True
                    signals.stage_warning.emit(self._current_stage_key)
                continue

            # Also catch plain WARNING: lines from scripts
            if line.startswith("WARNING:"):
                if self._current_stage_key:
                    self._stage_had_warning = True
                    signals.stage_warning.emit(self._current_stage_key)

            # ── UPLOAD AUTO — file not on Monday, upload immediately ──
            if line.startswith("UI_UPLOAD_AUTO:"):
                filename = line.replace("UI_UPLOAD_AUTO:", "").strip()
                signals.log.emit(f"  ▸ Auto-uploading: {filename}")
                self._proc.stdin.write("UPLOAD\n")
                self._proc.stdin.flush()
                continue

            # ── UPLOAD CONFIRM — file already on Monday, ask user ──
            if line.startswith("UI_UPLOAD_CONFIRM:"):
                signals.req_upload_confirm.emit(
                    line.replace("UI_UPLOAD_CONFIRM:", "").strip()
                )
                result = self._wait_for_result(key, timeout=120)
                if result is None:
                    return False
                self._proc.stdin.write(result + "\n")
                self._proc.stdin.flush()
                continue

            # ── MONDAY MISMATCH ──
            if line.startswith("UI_MONDAY_MISMATCH:"):
                parts = line.replace(
                    "UI_MONDAY_MISMATCH:", ""
                ).strip().split("|")
                signals.req_monday_mismatch.emit(
                    parts[0] if len(parts) > 0 else "",
                    parts[1] if len(parts) > 1 else ""
                )
                result = self._wait_for_result(key, timeout=120)
                if result is None:
                    return False
                self._proc.stdin.write(result + "\n")
                self._proc.stdin.flush()
                continue

            # ── XL FILE PATH (collect, show popup after stage done) ──
            if line.startswith("UI_XL_PATH:"):
                path = line.replace("UI_XL_PATH:", "").strip()
                self._xl_paths.append(path)
                signals.log.emit(f"  ▸ XL created: {os.path.basename(path)}")
                continue

            # ── REGULAR LOG LINE ──
            signals.log.emit(line)

        self._proc.wait()

        if self._stopped:
            signals.log.emit("STOPPED by user.")
            signals.stage_done.emit(key, False)
            return False

        success = self._proc.returncode == 0

        # If XL files were created, show popup after stage done
        if self._xl_paths:
            paths_str = "|".join(self._xl_paths)
            self._xl_paths = []
            signals.req_xl_complete.emit(paths_str)

        signals.stage_done.emit(key, success)
        return success


runner = ScriptRunner()


# =========================
# MAIN WINDOW
# =========================

class SAXWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SAX — Calcs Pipeline")
        self.setMinimumSize(920, 680)
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(1200, 720)
        self.move(
            (screen.width() - 1200) // 2,
            (screen.height() - 720) // 2
        )
        self.setStyleSheet(f"background-color:{BG};color:{TEXT};")

        self.project_root     = ""
        self.project_name     = ""
        self.project_number   = ""
        self.tot_status       = ""
        self.running          = False
        self._project_cache   = {}
        self.stage_buttons    = {}
        self.active_stages    = list(DEFAULT_STAGES)
        self.completed_stages = set()
        self._calcs_expanded  = False
        self._stage_seconds   = 0
        self._stage_clock     = QTimer()
        self._stage_clock.timeout.connect(self._tick_clock)
        self._stage_target    = 0
        self._stage_anim      = QTimer()
        self._stage_anim.timeout.connect(self._tick_stage_bar)
        self._total_seconds   = 0
        self._total_clock     = QTimer()
        self._total_clock.timeout.connect(self._tick_total_clock)
        self._total_clock.start(1000)
        self._pipeline_seconds  = 0
        self._pipeline_clock    = QTimer()
        self._pipeline_clock.timeout.connect(self._tick_pipeline_clock)
        self._stage_running     = False
        self._pipeline_running  = False
        self._shimmer_pos       = 0.0
        self._shimmer_timer     = QTimer()
        self._shimmer_timer.timeout.connect(self._tick_shimmer)
        self._pipe_index        = 0   # current stage index within the run
        self._pipe_total        = 0   # total stages in the current run

        # Connect all signals to main thread handlers
        signals.log.connect(self.append_log)
        signals.stage_done.connect(self.on_stage_done)
        signals.stage_warning.connect(lambda key: self._update_stage_dot(key, "warning"))
        signals.pipeline_progress.connect(self.set_pipeline_progress)
        signals.stage_progress.connect(self.set_stage_progress)
        signals.after_info.connect(self._after_info)
        signals.req_open_pdf.connect(self.handle_open_pdf)
        signals.req_bad_template.connect(self.handle_bad_template)
        signals.req_confirm_apn.connect(self.handle_confirm_apn)
        signals.req_confirm_tot.connect(self.handle_confirm_tot)
        signals.req_addr_mismatch.connect(self.handle_addr_mismatch)
        signals.req_monday_mismatch.connect(self.handle_monday_mismatch)
        signals.req_info_exists.connect(self.handle_info_exists)
        signals.req_upload_confirm.connect(self.handle_upload_confirm)
        signals.req_xl_complete.connect(self.handle_xl_complete)
        signals.req_xl_select.connect(self.handle_xl_select)
        signals.reset_bars.connect(self._reset_stage_bars)
        signals.req_tot_manual.connect(self.handle_tot_manual)
        signals.req_asce_exists.connect(self.handle_asce_exists)
        signals.req_seismic_exists.connect(self.handle_seismic_exists)
        signals.req_seismic_manual.connect(self.handle_seismic_manual)
        signals.req_location_exists.connect(self.handle_location_exists)
        signals.refresh_done.connect(self._after_refresh)
        signals.run_finished.connect(self._after_run_all)
        signals.req_workflow_update.connect(self._finish_load_silent)
        signals.stage_start.connect(self._on_stage_start)

        self._build_ui()
        self._build_stage_buttons(DEFAULT_STAGES, enabled=False)
        self._init_headless_state()

    # =========================
    # DIALOG HANDLERS
    # Each shows dialog then puts result into runner queue.
    # =========================

    def handle_open_pdf(self, pdf_path, pdf_name):
        dlg = OpenPDFDialog(self, pdf_name)
        if dlg.exec() == QDialog.Accepted:
            try:
                os.startfile(pdf_path)
            except Exception:
                pass
        runner.put_result("ok")

    def handle_bad_template(self, pdf_path):
        try:
            os.startfile(pdf_path)
        except Exception:
            pass
        dlg = ManualAddressDialog(self)
        if dlg.exec() == QDialog.Accepted:
            runner.put_result(dlg.result_address)
        else:
            runner.put_result("")

    def handle_confirm_apn(self, payload):
        parts        = payload.split("|")
        current_apn  = parts[0] if len(parts) > 0 else ""
        contract_pdf = parts[1] if len(parts) > 1 else ""
        padded       = parts[2] == "PADDED" if len(parts) > 2 else False
        dlg = APNDialog(self, current_apn, contract_pdf, padded=padded)
        if dlg.exec() == QDialog.Accepted:
            runner.put_result(dlg.result_apn)
        else:
            runner.put_result("CANCELLED")

    def handle_confirm_tot(self, tot_status):
        dlg = TOTConfirmDialog(self, tot_status)
        result = dlg.exec()
        if result == QDialog.Accepted:
            runner.put_result("CONFIRMED")
        elif result == 2:
            runner.put_result("OVERRIDE")
        else:
            runner.put_result("CONFIRMED")

    def handle_location_exists(self, path):
        dlg    = LocationExistsDialog(self, path)
        result = dlg.exec()
        runner.put_result("SKIP" if result == 2 else "RERUN")

    def handle_seismic_manual(self, pdf_path):
        dlg    = SeismicManualDialog(self, pdf_path)
        result = dlg.exec()
        runner.put_result("SKIP" if result == 2 else "DONE")

    def handle_seismic_exists(self, payload):
        parts    = payload.split("|")
        filename = parts[0].strip()
        date_str = parts[1].strip() if len(parts) > 1 else ""
        dlg      = SeismicExistsDialog(self, filename, date_str)
        result   = dlg.exec()
        runner.put_result("SKIP" if result == 2 else "RERUN")

    def handle_asce_exists(self, filename):
        dlg    = ASCEExistsDialog(self, filename)
        result = dlg.exec()
        runner.put_result("SKIP" if result == 2 else "RERUN")

    def handle_tot_manual(self, message):
        dlg = TOTManualDialog(self, message)
        runner.put_result(
            "Y" if dlg.exec() == QDialog.Accepted else "N"
        )

    def handle_addr_mismatch(self, info_addr, found_addr):
        dlg = AddressMismatchDialog(self, info_addr, found_addr)
        runner.put_result(
            "Y" if dlg.exec() == QDialog.Accepted else "N"
        )

    def handle_monday_mismatch(self, monday_name, local_name):
        dlg = MondayMismatchDialog(self, monday_name, local_name)
        runner.put_result(
            "Y" if dlg.exec() == QDialog.Accepted else "N"
        )

    def handle_info_exists(self, files_str):
        files  = files_str.split("|")
        dlg    = InfoExistsDialog(self, files)
        result = dlg.exec()
        if result == 3:
            runner.put_result("SKIP")
        elif result == 2:
            # Pass back the selected file path so 01_info.py knows which to overwrite
            selected = dlg.selected_file or files[-1]
            runner.put_result(f"OVERWRITE:{selected}")
        else:
            runner.put_result("NEW")

    def handle_xl_select(self, payload):
        parts     = payload.split("|")
        file_type = parts[0].strip()
        files     = [p.strip() for p in parts[1:] if p.strip()]
        if not files:
            runner.put_result("NEW")
            return
        dlg = XLSelectDialog(self, files, file_type)
        result = dlg.exec()
        if result == 2 and dlg.selected_file:
            runner.put_result(f"UPDATE:{dlg.selected_file}")
        else:
            runner.put_result("NEW")

    def handle_xl_complete(self, paths_str):
        paths = [p for p in paths_str.split("|") if p.strip()]
        try:
            from config import HEADLESS as _headless
        except:
            _headless = False
        dlg    = XLCompleteDialog(self, paths, headless=_headless)
        result = dlg.exec()
        if result == QDialog.Accepted:
            self.append_log(
                f"Opening: {', '.join(os.path.basename(p) for p in dlg.keep_open)}"
            )
            for p in dlg.keep_open:
                try:
                    os.startfile(p)
                except Exception as e:
                    self.append_log(f"ERROR opening {os.path.basename(p)}: {e}")
            runner.put_result("KEEP")
        else:
            self.append_log("XL files closed.")
            runner.put_result("CLOSE")
        self._stop_pipeline_clock(success=True)
        self.append_log("=== PIPELINE COMPLETE ===")

    def handle_upload_confirm(self, contract_path):
        """File already on Monday — ask whether to re-upload."""
        dlg    = UploadConfirmDialog(self, contract_path, contract_path)
        result = dlg.exec()
        if result == 2:
            runner.put_result("SKIP")
        else:
            runner.put_result("UPLOAD")

    # =========================
    # BUILD UI
    # =========================

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # LEFT PANEL
        left = QWidget()
        left.setFixedWidth(300)
        left.setStyleSheet(
            f"background-color:{PANEL};border-right:1px solid {BORDER};"
        )
        ll = QVBoxLayout(left)
        ll.setContentsMargins(16, 20, 16, 16)
        ll.setSpacing(8)

        title = QLabel("SAX")
        title.setFont(QFont("Arial", 22, QFont.Bold))
        title.setStyleSheet(f"color:{BLUE};")
        ll.addWidget(title)

        subtitle = QLabel("Structural Automation Xtension")
        subtitle.setFont(QFont("Arial", 9))
        subtitle.setStyleSheet(f"color:{SUBTEXT};")
        subtitle.setWordWrap(True)
        ll.addWidget(subtitle)
        ll.addSpacing(14)

        self._slabel(ll, "PROJECT")
        self.project_input = QComboBox()
        self.project_input.setEditable(True)
        self.project_input.setInsertPolicy(QComboBox.NoInsert)
        self.project_input.lineEdit().setPlaceholderText("Type or click ▼ to browse...")
        self.project_input.setStyleSheet(
            f"QComboBox{{background-color:{BG};color:{TEXT};"
            f"border:1px solid {BORDER};border-radius:6px;"
            f"padding:6px 10px;font-family:Arial;font-size:13px;}}"
            f"QComboBox:focus{{border-color:{BLUE};}}"
            f"QComboBox::drop-down{{border:none;width:24px;}}"
            f"QComboBox::down-arrow{{width:10px;height:10px;}}"
            f"QComboBox QAbstractItemView{{"
            f"background:{PANEL};color:{TEXT};border:1px solid {BORDER};"
            f"font-family:Arial;font-size:12px;padding:4px;"
            f"selection-background-color:{BLUE};selection-color:white;}}"
        )
        self.project_input.setMaxVisibleItems(30)
        self.project_input.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        completer = self.project_input.completer()
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self.project_input.lineEdit().returnPressed.connect(self.load_project)
        self.project_input.activated.connect(self._on_project_selected)
        ll.addWidget(self.project_input)

        self.project_name_label = QLabel("")
        self.project_name_label.setFont(QFont("Arial", 9))
        self.project_name_label.setStyleSheet(
            f"color:{GREEN};padding:2px 0;"
        )
        self.project_name_label.setWordWrap(True)
        ll.addWidget(self.project_name_label)

        self.tot_badge = QLabel("")
        self.tot_badge.setFont(QFont("Arial", 9, QFont.Bold))
        self.tot_badge.setStyleSheet(f"color:{SUBTEXT};")
        ll.addWidget(self.tot_badge)

        self.load_btn = QPushButton("LOAD PROJECT")
        self.load_btn.setStyleSheet(
            f"QPushButton{{background-color:{BTN_DEFAULT};color:{TEXT};"
            f"border:1px solid {BORDER};border-radius:6px;padding:8px;"
            f"font-family:Arial;font-size:12px;}}"
            f"QPushButton:hover{{background-color:{BTN_HOVER};"
            f"border-color:{BLUE};}}"
        )
        self.load_btn.clicked.connect(self.load_project)
        ll.addWidget(self.load_btn)

        open_row = QHBoxLayout()
        open_row.setSpacing(4)

        open_btn_style = (
            f"QPushButton{{background-color:{BTN_DEFAULT};color:{TEXT};"
            f"border:1px solid {BORDER};border-radius:6px;padding:6px 8px;"
            f"font-family:Arial;font-size:11px;text-align:left;}}"
            f"QPushButton:hover{{background-color:{BTN_HOVER};border-color:{BLUE};}}"
            f"QPushButton:disabled{{background-color:#2A2A3E;"
            f"color:{SUBTEXT};border-color:#333355;}}"
        )

        self.open_project_btn = QPushButton("📁  OPEN PROJECT")
        self.open_project_btn.setMinimumHeight(32)
        self.open_project_btn.setStyleSheet(open_btn_style)
        self.open_project_btn.setEnabled(False)
        self.open_project_btn.clicked.connect(self.open_project_folder)
        open_row.addWidget(self.open_project_btn)

        self.open_contract_btn = QPushButton("📝  OPEN CONTRACT")
        self.open_contract_btn.setMinimumHeight(32)
        self.open_contract_btn.setStyleSheet(open_btn_style)
        self.open_contract_btn.setEnabled(False)
        self.open_contract_btn.clicked.connect(self.open_contract_pdf)
        open_row.addWidget(self.open_contract_btn)

        ll.addLayout(open_row)

        self.upload_btn = QPushButton("▶▶  UPLOAD CONTRACT")
        self.upload_btn.setMinimumHeight(34)
        self.upload_btn.setStyleSheet(
            f"QPushButton{{background-color:{BTN_DEFAULT};color:{TEXT};"
            f"border:1px solid {BORDER};border-radius:8px;padding:11px 16px;"
            f"font-family:Arial;font-size:13px;font-weight:bold;text-align:left;}}"
            f"QPushButton:hover{{background-color:{BTN_HOVER};"
            f"border-color:{BLUE};}}"
            f"QPushButton:disabled{{background-color:#2A2A3E;"
            f"color:{SUBTEXT};border-color:#333355;}}"
        )
        self.upload_btn.setEnabled(False)
        self.upload_btn.clicked.connect(
            lambda: self.run_single("monday")
        )
        ll.addWidget(self.upload_btn)

        self.apn_btn = QPushButton("▶▶  APN VERIFICATION")
        self.apn_btn.setMinimumHeight(34)
        self.apn_btn.setStyleSheet(
            f"QPushButton{{background-color:{BTN_DEFAULT};color:{TEXT};"
            f"border:1px solid {BORDER};border-radius:8px;padding:11px 16px;"
            f"font-family:Arial;font-size:13px;font-weight:bold;text-align:left;}}"
            f"QPushButton:hover{{background-color:{BTN_HOVER};border-color:{BLUE};}}"
            f"QPushButton:disabled{{background-color:#2A2A3E;"
            f"color:{SUBTEXT};border-color:#333355;}}"
        )
        self.apn_btn.setEnabled(False)
        self.apn_btn.clicked.connect(lambda: self.run_single("apn", force=True))
        ll.addWidget(self.apn_btn)

        self.tot_btn = QPushButton("▶▶  TOT VERIFICATION")
        self.tot_btn.setMinimumHeight(34)
        self.tot_btn.setStyleSheet(
            f"QPushButton{{background-color:{BTN_DEFAULT};color:{TEXT};"
            f"border:1px solid {BORDER};border-radius:8px;padding:11px 16px;"
            f"font-family:Arial;font-size:13px;font-weight:bold;text-align:left;}}"
            f"QPushButton:hover{{background-color:{BTN_HOVER};border-color:{BLUE};}}"
            f"QPushButton:disabled{{background-color:#2A2A3E;"
            f"color:{SUBTEXT};border-color:#333355;}}"
        )
        self.tot_btn.setEnabled(False)
        self.tot_btn.clicked.connect(lambda: self.run_single("tot", force=True))
        ll.addWidget(self.tot_btn)

        self.setup_calcs_btn = SplitButton("SETUP CALCS")
        self.setup_calcs_btn.set_enabled(False)
        self.setup_calcs_btn.run_clicked.connect(self.run_all)
        self.setup_calcs_btn.arrow_clicked.connect(
            self._show_stages_popup
        )
        ll.addWidget(self.setup_calcs_btn)

        self.setup_revit_btn = QPushButton("▶▶  SETUP REVIT")
        self.setup_revit_btn.setMinimumHeight(34)
        self.setup_revit_btn.setStyleSheet(
            f"QPushButton{{background-color:{PANEL};color:#555577;"
            f"border:1px solid #333355;border-radius:8px;padding:11px 16px;"
            f"font-family:Arial;font-size:13px;font-weight:bold;text-align:left;}}"
        )
        self.setup_revit_btn.setEnabled(False)
        ll.addWidget(self.setup_revit_btn)

        ll.addStretch()

        self.refresh_btn = QPushButton("⟳  Refresh Projects")
        self.refresh_btn.setStyleSheet(
            f"QPushButton{{background-color:{BTN_DEFAULT};color:{SUBTEXT};"
            f"border:1px solid #333355;border-radius:6px;padding:6px;"
            f"font-family:Arial;font-size:11px;}}"
            f"QPushButton:hover{{color:{TEXT};border-color:{BORDER};}}"
        )
        self.refresh_btn.clicked.connect(self.refresh_projects)
        ll.addWidget(self.refresh_btn)

        self.clean_locks_btn = QPushButton("🔓  Clean Excel Locks")
        self.clean_locks_btn.setStyleSheet(
            f"QPushButton{{background-color:{BTN_DEFAULT};color:{SUBTEXT};"
            f"border:1px solid #333355;border-radius:6px;padding:6px;"
            f"font-family:Arial;font-size:11px;}}"
            f"QPushButton:hover{{color:{YELLOW};border-color:{YELLOW};}}"
        )
        self.clean_locks_btn.setEnabled(False)
        self.clean_locks_btn.clicked.connect(self.clean_excel_locks)
        ll.addWidget(self.clean_locks_btn)

        self.headless_btn = QPushButton("🟢  Work in Background: ON")
        self.headless_btn.setCheckable(True)
        self.headless_btn.setChecked(True)
        self.headless_btn.setStyleSheet(
            f"QPushButton{{background-color:{BTN_DEFAULT};"
            f"color:{SUBTEXT};border:1px solid #333355;"
            f"border-radius:6px;padding:6px;"
            f"font-family:Arial;font-size:11px;}}"
            f"QPushButton:checked{{background-color:#1A3A2A;"
            f"color:{GREEN};border-color:{GREEN};}}"
            f"QPushButton:hover{{color:{TEXT};border-color:{BORDER};}}"
        )
        self.headless_btn.clicked.connect(self.toggle_headless)
        ll.addWidget(self.headless_btn)

        root.addWidget(left)

        # RIGHT PANEL
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(20, 20, 20, 16)
        rl.setSpacing(8)

        # Total runtime clock
        th = QHBoxLayout()
        self.total_time_label = QLabel("TOTAL TIME")
        self.total_time_label.setFont(QFont("Arial", 8, QFont.Bold))
        self.total_time_label.setStyleSheet(f"color:{SUBTEXT};letter-spacing:1px;")
        th.addWidget(self.total_time_label)
        th.addStretch()
        self.total_timer_label = QLabel("00:00")
        self.total_timer_label.setFont(QFont("Courier New", 13, QFont.Bold))
        self.total_timer_label.setStyleSheet(f"color:{GREEN};")
        self.total_timer_label.setAlignment(Qt.AlignRight)
        th.addWidget(self.total_timer_label)
        rl.addLayout(th)

        # Stage indicator — horizontal dots above pipeline bar
        self.stage_indicator_widget = QWidget()
        self.stage_indicator_layout = FlowLayout(self.stage_indicator_widget, margin=0, spacing=14)
        self._stage_dot_labels = {}  # key -> (dot_label, txt_label)
        rl.addWidget(self.stage_indicator_widget)
        rl.addSpacing(4)

        # Pipeline bar
        ph = QHBoxLayout()
        pl = QLabel("PIPELINE PROGRESS")
        pl.setFont(QFont("Arial", 8, QFont.Bold))
        pl.setStyleSheet(f"color:{SUBTEXT};letter-spacing:1px;")
        ph.addWidget(pl)
        ph.addStretch()
        self.pipeline_clock_label = QLabel("00:00")
        self.pipeline_clock_label.setFont(QFont("Courier New", 9))
        self.pipeline_clock_label.setStyleSheet(f"color:{BLUE};")
        ph.addWidget(self.pipeline_clock_label)
        self.pipeline_pct_label = QLabel("—")
        self.pipeline_pct_label.setFont(QFont("Arial", 9))
        self.pipeline_pct_label.setStyleSheet(f"color:{SUBTEXT};")
        self.pipeline_pct_label.setAlignment(Qt.AlignRight)
        ph.addWidget(self.pipeline_pct_label)
        rl.addLayout(ph)
        self.pipeline_bar = QProgressBar()
        self.pipeline_bar.setRange(0, 100)
        self.pipeline_bar.setValue(0)
        self.pipeline_bar.setTextVisible(False)
        self.pipeline_bar.setFixedHeight(12)
        self.pipeline_bar.setStyleSheet(self._bar_style(BLUE, radius=6))
        rl.addWidget(self.pipeline_bar)
        rl.addSpacing(6)

        # Stage bar — shows current stage name + timer
        sh = QHBoxLayout()
        sl = QLabel("CURRENT STAGE")
        sl.setFont(QFont("Arial", 8, QFont.Bold))
        sl.setStyleSheet(f"color:{SUBTEXT};letter-spacing:1px;")
        sh.addWidget(sl)
        self.current_stage_name_label = QLabel("—")
        self.current_stage_name_label.setFont(QFont("Arial", 9, QFont.Bold))
        self.current_stage_name_label.setStyleSheet(f"color:{TEXT};")
        sh.addWidget(self.current_stage_name_label)
        sh.addStretch()
        self.stage_timer_label = QLabel("00:00")
        self.stage_timer_label.setFont(QFont("Courier New", 9))
        self.stage_timer_label.setStyleSheet(f"color:{BLUE};")
        sh.addWidget(self.stage_timer_label)
        self.stage_step_label = QLabel("—")
        self.stage_step_label.setFont(QFont("Arial", 9))
        self.stage_step_label.setStyleSheet(f"color:{SUBTEXT};")
        self.stage_step_label.setAlignment(Qt.AlignRight)
        sh.addWidget(self.stage_step_label)
        rl.addLayout(sh)
        self.stage_bar = QProgressBar()
        self.stage_bar.setRange(0, 100)
        self.stage_bar.setValue(0)
        self.stage_bar.setTextVisible(False)
        self.stage_bar.setFixedHeight(8)
        self.stage_bar.setStyleSheet(self._bar_style(GREEN, radius=4))
        rl.addWidget(self.stage_bar)
        rl.addSpacing(8)

        self._slabel(rl, "STATUS LOG")
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet(
            f"QTextEdit{{background-color:{BG};color:{TEXT};"
            f"border:1px solid {BORDER};border-radius:8px;"
            f"padding:12px;font-family:Courier New;font-size:14px;}}"
        )
        rl.addWidget(self.log_display)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        clear_btn = QPushButton("Clear Log")
        clear_btn.setFixedWidth(90)
        clear_btn.setStyleSheet(
            f"QPushButton{{background-color:{BTN_DEFAULT};"
            f"color:{SUBTEXT};border:1px solid {BORDER};"
            f"border-radius:4px;padding:5px 10px;font-size:11px;}}"
            f"QPushButton:hover{{color:{TEXT};}}"
        )
        clear_btn.clicked.connect(self.log_display.clear)
        self.stop_btn = QPushButton("■  Stop")
        self.stop_btn.setFixedWidth(90)
        self.stop_btn.setStyleSheet(
            f"QPushButton{{background-color:#3A1111;color:{RED};"
            f"border:1px solid {RED};border-radius:4px;"
            f"padding:5px 10px;font-size:11px;font-weight:bold;}}"
            f"QPushButton:hover{{background-color:#4A1A1A;}}"
            f"QPushButton:disabled{{background-color:{PANEL};"
            f"color:#553333;border-color:#443333;}}"
        )
        self.stop_btn.setEnabled(True)
        self.stop_btn.clicked.connect(self.stop_pipeline)
        btn_row.addStretch()
        btn_row.addWidget(clear_btn)
        btn_row.addWidget(self.stop_btn)
        rl.addLayout(btn_row)
        root.addWidget(right, 1)

    def _slabel(self, layout, text):
        lbl = QLabel(text)
        lbl.setFont(QFont("Arial", 8, QFont.Bold))
        lbl.setStyleSheet(f"color:{SUBTEXT};letter-spacing:1px;")
        layout.addWidget(lbl)

    def _bar_style(self, color, radius=5):
        return (
            f"QProgressBar{{background-color:{BTN_DEFAULT};"
            f"border-radius:{radius}px;border:none;}}"
            f"QProgressBar::chunk{{background-color:{color};"
            f"border-radius:{radius}px;}}"
        )

    def _bar_shimmer_style(self, color, radius, pos):
        """Green fill with a light band sweeping across the FILLED length."""
        hi   = "#B6F7CF"
        band = 0.16
        raw  = [(0.0, color), (pos - band, color), (pos, hi),
                (pos + band, color), (1.0, color)]
        raw  = [(max(0.0, min(1.0, p)), c) for p, c in raw]
        raw.sort(key=lambda s: s[0])
        cleaned, last = [], -1.0
        for p, c in raw:
            if p <= last:
                p = min(1.0, last + 0.001)
            cleaned.append((p, c))
            last = p
        grad = ", ".join(f"stop:{p:.3f} {c}" for p, c in cleaned)
        return (
            f"QProgressBar{{background-color:{BTN_DEFAULT};"
            f"border-radius:{radius}px;border:none;}}"
            f"QProgressBar::chunk{{border-radius:{radius}px;"
            f"background-color:qlineargradient(x1:0,y1:0,x2:1,y2:0,{grad});}}"
        )

    def _start_shimmer(self):
        self._shimmer_pos = 0.0
        if not self._shimmer_timer.isActive():
            self._shimmer_timer.start(70)

    def _stop_shimmer(self):
        if self._shimmer_timer.isActive():
            self._shimmer_timer.stop()
        # restore solid green, keeping each bar's current fill
        self.pipeline_bar.setStyleSheet(self._bar_style(GREEN, radius=6))
        self.stage_bar.setStyleSheet(self._bar_style(GREEN, radius=4))

    def _tick_shimmer(self):
        self._shimmer_pos += 0.035
        if self._shimmer_pos > 1.0:
            self._shimmer_pos = 0.0
        p = self._shimmer_pos
        self.pipeline_bar.setStyleSheet(self._bar_shimmer_style(GREEN, 6, p))
        self.stage_bar.setStyleSheet(self._bar_shimmer_style(GREEN, 4, p))

    def _show_stages_popup(self):
        """Show floating stage list as a proper popup menu."""
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction

        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu{{background-color:{PANEL};color:{TEXT};"
            f"border:1px solid {BORDER};border-radius:8px;padding:4px;}}"
            f"QMenu::item{{padding:8px 16px;font-family:Arial;font-size:13px;}}"
            f"QMenu::item:selected{{background-color:{BTN_HOVER};color:{GREEN};}}"
            f"QMenu::item:disabled{{color:{SUBTEXT};}}"
            f"QMenu::separator{{height:1px;background:{BORDER};margin:2px 8px;}}"
        )

        for key in self.active_stages:
            label  = STAGE_LABELS.get(key, key)
            action = QAction(label, self)
            btn    = self.stage_buttons.get(key)
            action.setEnabled(True)
            action.triggered.connect(
                lambda checked=False, k=key: self.run_single(k)
            )
            menu.addAction(action)

        # Show below the Setup Calcs button
        btn_pos  = self.setup_calcs_btn.mapToGlobal(
            self.setup_calcs_btn.rect().bottomLeft()
        )
        menu.exec(btn_pos)

    def _toggle_calcs_stages(self):
        pass  # kept for compatibility

    def _build_stage_dots_greyed(self):
        """Show both TOT and Normal stages greyed — pre-TOT determination."""
        all_stages = ["apn", "tot", "tot_location", "tot_seismic", "tot_lat", "tot_vert"]
        while self.stage_indicator_layout.count():
            item = self.stage_indicator_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._stage_dot_labels = {}

        for i, key in enumerate(all_stages):
            label = STAGE_LABELS.get(key, key)
            short = label.split("—")[-1].strip() if "—" in label else label
            dot_widget = QWidget()
            dot_layout = QHBoxLayout(dot_widget)
            dot_layout.setContentsMargins(0, 0, 0, 0)
            dot_layout.setSpacing(3)
            dot = QLabel("⬜")
            dot.setFont(QFont("Arial", 8))
            dot.setStyleSheet(f"color:#333355;")
            txt = QLabel(short)
            txt.setFont(QFont("Arial", 8))
            txt.setStyleSheet(f"color:#333355;")
            dot_layout.addWidget(dot)
            dot_layout.addWidget(txt)
            self.stage_indicator_layout.addWidget(dot_widget)
            self._stage_dot_labels[key] = (dot, txt)

    def _build_stage_dots(self, stages):
        """Build grid stage indicator dots above pipeline bar — 3 per row."""
        while self.stage_indicator_layout.count():
            item = self.stage_indicator_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._stage_dot_labels = {}

        for i, key in enumerate(stages):
            label = STAGE_LABELS.get(key, key)
            short = label.split("—")[-1].strip() if "—" in label else label
            dot_widget = QWidget()
            dot_layout = QHBoxLayout(dot_widget)
            dot_layout.setContentsMargins(0, 0, 0, 0)
            dot_layout.setSpacing(3)
            dot = QLabel("⬜")
            dot.setFont(QFont("Arial", 8))
            dot.setStyleSheet(f"color:{SUBTEXT};")
            txt = QLabel(short)
            txt.setFont(QFont("Arial", 8))
            txt.setStyleSheet(f"color:{SUBTEXT};")
            dot_layout.addWidget(dot)
            dot_layout.addWidget(txt)
            self.stage_indicator_layout.addWidget(dot_widget)
            self._stage_dot_labels[key] = (dot, txt)

    def _update_stage_dot(self, key, state):
        """state: 'running', 'done', 'warning', 'failed'"""
        if key not in self._stage_dot_labels:
            return
        dot, txt = self._stage_dot_labels[key]
        if state == "done":
            dot.setText("✅")
            txt.setStyleSheet(f"color:{GREEN};")
        elif state == "running":
            dot.setText("▶")
            txt.setStyleSheet(f"color:{BLUE};font-weight:bold;")
        elif state == "warning":
            dot.setText("🟠")
            txt.setStyleSheet(f"color:#FF8800;")
        elif state == "failed":
            dot.setText("❌")
            txt.setStyleSheet(f"color:{RED};")

    def _build_stage_buttons(self, stages, enabled=True):
        # Stage buttons are now only used for status tracking
        # Visual list is shown via floating popup menu
        self.stage_buttons = {}
        for key in stages:
            btn = StageButton(key)
            if key not in COMING_SOON:
                btn.clicked.connect(
                    lambda checked, k=key: self.run_single(k)
                )
                if enabled:
                    btn.set_enabled_active(True)
            self.stage_buttons[key] = btn

    def _re_enable_ui(self):
        self.stop_btn.setEnabled(True)
        self.load_btn.setEnabled(True)
        if not self.running:
            self._stop_clock()
            self.setup_calcs_btn.set_enabled(True)
            self.upload_btn.setEnabled(True)
            self.open_project_btn.setEnabled(True)
            self.open_contract_btn.setEnabled(True)
            self.apn_btn.setEnabled(True)
            self.tot_btn.setEnabled(True)
            self.clean_locks_btn.setEnabled(True)
            for btn in self.stage_buttons.values():
                if btn.key not in COMING_SOON:
                    btn.set_enabled_active(True)

    # =========================
    # LOAD PROJECT
    # =========================

    def populate_projects(self, projects=None):
        """Load project list from cache into dropdown — instant."""
        items = get_project_list()
        self.project_input.blockSignals(True)
        self.project_input.clear()
        self.project_input.addItems(items)
        self.project_input.setCurrentIndex(-1)
        self.project_input.lineEdit().clear()
        # Re-apply completer after clear() disconnects it
        completer = self.project_input.completer()
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.project_input.blockSignals(False)

    def refresh_projects(self):
        """Scan only 26-XXX for new projects beyond last cached, update dropdown."""
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("⟳  Scanning...")
        self.append_log("Checking 26-XXX for new projects...")

        def worker():
            existing, new_entries = scan_new_projects()
            if new_entries:
                combined = existing + new_entries
                save_cache(combined)
                signals.log.emit(
                    f"  ▸ {len(new_entries)} new project(s) added:"
                )
                for p in new_entries:
                    label = f"{p['number']} — {p['name']}" if p.get('name') else p['number']
                    signals.log.emit(f"      {label}")
            else:
                signals.log.emit("  ▸ No new projects found")
            # emit a signal (thread-safe) so the dropdown repopulates on the GUI thread.
            # QTimer.singleShot does NOT fire from a worker thread (no event loop there).
            signals.refresh_done.emit()

        threading.Thread(target=worker, daemon=True).start()

    def _after_refresh(self):
        self.populate_projects()
        self.project_input.update()
        self.project_input.repaint()
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("⟳  Refresh Projects")
        self.append_log("Project list updated — Done.")

    def _on_project_selected(self, index):
        """User picked a project from the dropdown."""
        text = self.project_input.itemText(index)
        self.project_input.lineEdit().setText(text.split(" — ")[0].strip())

    def _init_headless_state(self):
        """Always default to background ON at every launch — force HEADLESS=True."""
        try:
            cfg = os.path.join(SHARED_DIR, "config.py")
            with open(cfg, "r", encoding="utf-8") as f:
                content = f.read()
            if "HEADLESS = False" in content:
                content = content.replace("HEADLESS = False", "HEADLESS = True")
                with open(cfg, "w", encoding="utf-8") as f:
                    f.write(content)
        except Exception:
            pass
        self.headless_btn.setChecked(True)
        self.headless_btn.setText("🟢  Work in Background: ON")

    def toggle_headless(self):
        checked = self.headless_btn.isChecked()
        # Update config.py on disk
        config_path = os.path.join(SHARED_DIR, "config.py")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()
            if checked:
                content = content.replace("HEADLESS = False", "HEADLESS = True")
                self.headless_btn.setText("🟢  Work in Background: ON")
                self.append_log("Work in Background: ON — browsers will run silently")
            else:
                content = content.replace("HEADLESS = True", "HEADLESS = False")
                self.headless_btn.setText("⬛  Work in Background: OFF")
                self.append_log("Work in Background: OFF — browsers will be visible")
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            self.append_log(f"ERROR: Could not update config: {e}")

    def clean_excel_locks(self):
        if not self.project_root:
            return
        from config import cleanup_xl_locks, get_calc_folder
        calc_folder = get_calc_folder(self.project_root)
        removed     = cleanup_xl_locks(calc_folder)
        if removed:
            self.append_log(f"Removed {len(removed)} lock file(s): {', '.join(removed)}")
        else:
            self.append_log("No Excel lock files found.")

    def open_contract_pdf(self):
        from config import read_info
        info_data, _ = read_info(self.project_root, self.project_number)
        pdf = info_data.get("CONTRACT_PDF", "")
        if pdf and os.path.exists(pdf):
            os.startfile(pdf)
        else:
            self.append_log("WARNING: Contract PDF not found in INFO file.")

    def open_project_folder(self):
        if self.project_root and os.path.exists(self.project_root):
            os.startfile(self.project_root)
        else:
            self.append_log("ERROR: Project folder not found.")

    def load_project(self):
        pn = self.project_input.lineEdit().text().strip().split(" — ")[0].strip()
        if not pn:
            self.append_log("ERROR: Enter a project number.")
            return
        project_root, project_name = find_project(pn)
        if not project_root:
            self.project_name_label.setText("Project not found.")
            self.project_name_label.setStyleSheet(f"color:{RED};")
            self.append_log(f"ERROR: No project found for {pn}")
            return

        self.project_number   = pn
        self.project_root     = project_root
        self.project_name     = project_name
        self.completed_stages = set()
        self.project_name_label.setText(project_name)
        self.project_name_label.setStyleSheet(f"color:{GREEN};")
        # Reset total clock for new project
        self._total_seconds = 0
        self.total_timer_label.setText("00:00")
        self.total_time_label.setText(f"TOTAL TIME — Project #: {self.project_number} {self.project_name}")
        self._pipeline_seconds = 0
        self.pipeline_clock_label.setText("00:00")
        self.pipeline_clock_label.setStyleSheet(f"color:{BLUE};")
        self.append_log(f"Project loaded: {project_name}")
        self.append_log("--- Running 01 — Project Info ---")
        self.load_btn.setEnabled(False)
        self.setup_calcs_btn.set_enabled(False)
        self.upload_btn.setEnabled(False)
        self.open_project_btn.setEnabled(False)
        self.open_contract_btn.setEnabled(False)
        self.apn_btn.setEnabled(False)
        self.tot_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._reset_stage_bars()

        def run_info():
            success = runner.run("info", pn)
            if success:
                self.completed_stages.add("info")
            signals.after_info.emit(success)

        threading.Thread(target=run_info, daemon=True).start()

    def _after_info(self, success):
        self.stop_btn.setEnabled(True)
        self.load_btn.setEnabled(True)
        if not success:
            self.append_log("ERROR: INFO stage failed.")
        self._prefill_completed()
        self._finish_load()

    def _prefill_completed(self):
        """Mark stages already done (from the INFO file) so they're not re-run
        as prerequisites when you click a later stage."""
        try:
            info = get_info_data(self.project_root, self.project_number)
        except Exception:
            return
        if not info:
            return
        if info.get("VERIFIED_APN", "").strip():
            self.completed_stages.add("apn")
        if info.get("TOT", "").strip():
            self.completed_stages.add("tot")
        if info.get("SEISMIC_SS", "").strip():
            self.completed_stages.add("asce")

    def _finish_load(self):
        self.stop_btn.setEnabled(True)
        info_data = get_info_data(self.project_root, self.project_number)
        tot = info_data.get("TOT", "").strip()
        self.tot_status = tot
        if tot == "Y":
            self.tot_badge.setText("⬡  TOT WORKFLOW")
            self.tot_badge.setStyleSheet(f"color:{YELLOW};")
            self.append_log("TOT: Y — TOT workflow loaded")
            self.active_stages = list(TOT_STAGES)
            self._build_stage_buttons(TOT_STAGES, enabled=True)
            self._build_stage_dots(TOT_STAGES)
        elif tot == "N":
            self.tot_badge.setText("⬡  NORMAL WORKFLOW")
            self.tot_badge.setStyleSheet(f"color:{BLUE};")
            self.append_log("TOT: N — Normal workflow loaded")
            self.active_stages = list(NORMAL_STAGES)
            self._build_stage_buttons(NORMAL_STAGES, enabled=True)
            self._build_stage_dots(NORMAL_STAGES)
        else:
            self.tot_badge.setText("⬡  TOT unknown — run APN & TOT first")
            self.tot_badge.setStyleSheet(f"color:{SUBTEXT};")
            self.append_log("TOT not yet determined.")
            self.active_stages = ["apn", "tot"]
            self._build_stage_buttons(["apn", "tot"], enabled=True)
            # Show all TOT stages greyed — will update live when TOT confirmed
            self._build_stage_dots_greyed()
        self._reset_stage_bars()
        self.setup_calcs_btn.set_enabled(True)
        self.upload_btn.setEnabled(True)
        self.open_project_btn.setEnabled(True)
        self.open_contract_btn.setEnabled(True)
        self.apn_btn.setEnabled(True)
        self.tot_btn.setEnabled(True)

    # =========================
    # PROGRESS & CLOCK
    # =========================

    def _reset_stage_bars(self):
        self.stage_bar.setValue(0)
        self._stage_target = 0
        self.stage_step_label.setText("—")
        self.stage_bar.setStyleSheet(self._bar_style(GREEN, radius=4))
        self._start_clock()

    # Clocks are driven by the single main-thread total-clock tick below, using
    # flags. QTimer.start() from a worker thread is silently ignored, so the
    # stage/pipeline timers must NOT rely on their own QTimers.
    def _start_clock(self):
        self._stage_seconds = 0
        self._stage_running = True

    def _stop_clock(self):
        self._stage_running = False

    def _start_pipeline_clock(self):
        self._pipeline_seconds = 0
        self._pipeline_running = True

    def _stop_pipeline_clock(self, success=True):
        self._pipeline_running = False

    def _tick_clock(self):
        pass  # unused — driven by _tick_total_clock

    def _tick_pipeline_clock(self):
        pass  # unused — driven by _tick_total_clock

    def _tick_total_clock(self):
        self._total_seconds += 1
        self.total_timer_label.setText(
            f"{self._total_seconds // 60:02d}:{self._total_seconds % 60:02d}"
        )
        if self._stage_running:
            self._stage_seconds += 1
            self.stage_timer_label.setText(
                f"{self._stage_seconds // 60:02d}:{self._stage_seconds % 60:02d}"
            )
        if self._pipeline_running:
            self._pipeline_seconds += 1
            self.pipeline_clock_label.setText(
                f"{self._pipeline_seconds // 60:02d}:{self._pipeline_seconds % 60:02d}"
            )

    def _on_stage_start(self, idx, total):
        """Stage began — pipeline fill starts at the completed-stages point; the
        stage's own step progress then fills its slice (see set_stage_progress)."""
        if total <= 0:
            return
        self._pipe_index = idx
        self._pipe_total = total
        self.pipeline_bar.setValue(int((idx / total) * 100))
        self.pipeline_pct_label.setText(f"STAGES {idx + 1}/{total}")

    def set_pipeline_progress(self, current, total):
        if total == 0:
            return
        pct = int((current / total) * 100)
        self.pipeline_bar.setValue(pct)
        self.pipeline_pct_label.setText(f"STAGES {current}/{total}")
        if current == total:
            self.pipeline_bar.setStyleSheet(
                self._bar_style(GREEN, radius=6)
            )

    def set_stage_progress(self, step, total):
        if total == 0:
            return
        self._stage_target = int((step / total) * 100)
        self.stage_step_label.setText(f"STEPS {step}/{total}")
        if not self._stage_anim.isActive():
            self._stage_anim.start(20)
        if step == total:
            self.stage_bar.setStyleSheet(
                self._bar_style(GREEN, radius=4)
            )
        # Pipeline fill = (completed stages + this stage's fraction) / total stages
        if self._pipe_total > 0:
            frac = step / total
            pct  = int(((self._pipe_index + frac) / self._pipe_total) * 100)
            self.pipeline_bar.setValue(pct)

    def _tick_stage_bar(self):
        current = self.stage_bar.value()
        target  = self._stage_target
        if current < target:
            self.stage_bar.setValue(current + 1)
        else:
            self._stage_anim.stop()

    # =========================
    # LOGGING
    # =========================

    def append_log(self, message):
        if not message.strip():
            return
        # Pipeline header lines — large bright green
        if message.startswith("===") or message.startswith("--- Running"):
            self.log_display.append(
                f'<span style="color:#00FF88;font-family:Courier New;'
                f'font-size:15px;font-weight:bold;">{message}</span>'
            )
            # Update current stage name label
            if message.startswith("--- Running"):
                stage_name = message.replace("--- Running", "").replace("---", "").strip()
                self.current_stage_name_label.setText(stage_name)
                # Find key and mark dot as running
                for key, lbl in STAGE_LABELS.items():
                    if lbl == stage_name:
                        self._update_stage_dot(key, "running")
                        break
            return
        if any(w in message for w in ["ERROR", "FAILED", "EXCEPTION"]):
            color = RED
        elif any(w in message for w in [
            "SUCCESS", "COMPLETE", "DONE",
            "UPLOADED", "FOUND", "CREATED", "SAVED"
        ]):
            color = GREEN
        elif any(w in message for w in ["WARNING", "WARN", "MISMATCH"]):
            color = YELLOW
        elif message.startswith("  ▸") or message.startswith("▸"):
            color = BLUE
        else:
            color = TEXT
        self.log_display.append(
            f'<span style="color:{color};font-family:Courier New;">'
            f'{message}</span>'
        )

    # =========================
    # STAGE DONE
    # =========================

    def on_stage_done(self, key, success):
        if success:
            self.completed_stages.add(key)
            # Snap the stage bar to full on completion, even if the script
            # emitted fewer sub-steps than declared (e.g. skipped upload).
            steps = SCRIPT_STEPS.get(key, [])
            if steps:
                self._stage_target = 100
                self.stage_bar.setValue(100)
                self.stage_step_label.setText(f"STEPS {len(steps)}/{len(steps)}")
            if runner._stage_had_warning:
                self._update_stage_dot(key, "warning")
            else:
                self._update_stage_dot(key, "done")
        else:
            self._update_stage_dot(key, "failed")
        btn = self.stage_buttons.get(key)
        if btn:
            if success:
                btn.set_success()
            else:
                btn.set_failed()
        QTimer.singleShot(0, self._re_enable_ui)

    # =========================
    # STOP
    # =========================

    def stop_pipeline(self):
        runner.stop()
        self.running = False
        self._stop_pipeline_clock(success=False)
        self.append_log("=== PIPELINE STOPPED BY USER ===")
        QTimer.singleShot(200, self._re_enable_ui)

    # =========================
    # DEPENDENCY CHECK
    # =========================

    def _check_dependencies(self, key):
        for dep in DEPENDENCIES.get(key, []):
            if dep not in self.completed_stages:
                return False, dep
        return True, None

    # =========================
    # RUN SINGLE
    # =========================

    def _ordered_prereqs(self, key):
        """Prerequisites for key in dependency order (deps first), deduped."""
        ordered = []
        def add(k):
            for dep in DEPENDENCIES.get(k, []):
                add(dep)
                if dep not in ordered:
                    ordered.append(dep)
        add(key)
        return ordered

    def run_single(self, key, force=False):
        if not self.project_number:
            self.append_log("ERROR: No project loaded.")
            return
        if key in COMING_SOON:
            return
        if self.running:
            return

        # No dependency popup. Build the chain: any prerequisites not already
        # done (in order), then the clicked stage. Each script skips itself if
        # already complete. Only the clicked stage honors `force`.
        chain = [d for d in self._ordered_prereqs(key)
                 if d not in self.completed_stages and d not in COMING_SOON]
        chain.append(key)
        self._run_stage_chain(chain, force_stage=key if force else None)

    def _run_stage_chain(self, chain, force_stage=None):
        self.running = True
        self._run_failed = False
        self.setup_calcs_btn.set_enabled(False)
        self.upload_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.pipeline_bar.setStyleSheet(self._bar_style(BLUE, radius=6))
        self.pipeline_bar.setValue(0)
        self._total_clock.start(1000)
        self._start_pipeline_clock()
        self._start_shimmer()
        self._reset_stage_bars()
        if len(chain) > 1:
            self.append_log(
                "=== Running: "
                + " → ".join(STAGE_LABELS.get(s, s) for s in chain)
                + " ==="
            )

        def worker():
            completed = 0
            for idx, k in enumerate(chain):
                if not self.running:
                    break
                runner._current_stage_key = k
                runner._stage_had_warning = False
                btn = self.stage_buttons.get(k)
                if btn:
                    btn.set_running()
                signals.log.emit(f"--- Running {STAGE_LABELS.get(k, k)} ---")
                signals.reset_bars.emit()
                signals.stage_start.emit(idx, len(chain))
                success = runner.run(
                    k, self.project_number, force=(k == force_stage)
                )
                completed += 1
                signals.pipeline_progress.emit(completed, len(chain))
                if success:
                    self.completed_stages.add(k)
                else:
                    signals.log.emit(
                        f"STOPPED — {STAGE_LABELS.get(k, k)} failed."
                    )
                    self._run_failed = True
                    break
            self.running = False
            signals.run_finished.emit()

        threading.Thread(target=worker, daemon=True).start()

    # =========================
    # SETUP CALCS
    # =========================

    def run_all(self):
        if self.running:
            return
        if not self.project_number:
            self.append_log("ERROR: No project loaded.")
            return

        stages = self.active_stages
        total  = len(stages)
        self.running = True
        self._run_failed = False
        self.setup_calcs_btn.set_enabled(False)
        self.stop_btn.setEnabled(True)
        self.pipeline_bar.setStyleSheet(self._bar_style(BLUE, radius=6))
        self.pipeline_bar.setValue(0)
        self._total_clock.start(1000)

        # Build stage dots
        self._build_stage_dots(stages)
        self._start_pipeline_clock()
        self._start_shimmer()

        self.append_log(f"=== SETUP CALCS — {total} stages ===")
        for i, stage in enumerate(stages, 1):
            label = STAGE_LABELS.get(stage, stage)
            self.append_log(f"  {i}. {label}")

        def worker():
            completed = 0
            stages_list = list(stages)  # mutable copy
            i = 0
            while i < len(stages_list):
                if not self.running:
                    break
                key = stages_list[i]
                i += 1
                if key in COMING_SOON:
                    completed += 1
                    signals.pipeline_progress.emit(completed, len(stages_list))
                    continue
                btn = self.stage_buttons.get(key)
                if btn:
                    btn.set_running()
                runner._current_stage_key = key
                runner._stage_had_warning = False
                signals.log.emit(
                    f"--- Running {STAGE_LABELS.get(key, key)} ---"
                )
                signals.reset_bars.emit()
                signals.stage_start.emit(completed, len(stages_list))
                success = runner.run(key, self.project_number)
                completed += 1
                signals.pipeline_progress.emit(completed, len(stages_list))
                if not success:
                    signals.log.emit(
                        f"PIPELINE STOPPED — "
                        f"{STAGE_LABELS.get(key, key)} failed."
                    )
                    self._run_failed = True
                    break

                # After TOT completes, check TOT status and extend pipeline
                if key == "tot":
                    info_data = get_info_data(
                        self.project_root, self.project_number
                    )
                    tot = info_data.get("TOT", "").strip()
                    if tot == "Y":
                        remaining = ["tot_location", "tot_seismic", "tot_lat", "tot_vert"]
                    else:
                        remaining = ["asce", "lat", "vert"]
                    # Only add stages not already in list
                    for s in remaining:
                        if s not in stages_list:
                            stages_list.append(s)
                    # Rebuild stage buttons for new workflow on main thread (via signal)
                    signals.req_workflow_update.emit(tot)

            self.running = False
            signals.run_finished.emit()

        threading.Thread(target=worker, daemon=True).start()

    def _finish_load_silent(self, tot):
        """Update workflow badges and stage buttons after TOT determined mid-pipeline."""
        if tot == "Y":
            self.tot_badge.setText("⬡  TOT WORKFLOW")
            self.tot_badge.setStyleSheet(f"color:{YELLOW};")
            self.active_stages = list(TOT_STAGES)
            self._build_stage_buttons(TOT_STAGES, enabled=False)
            self._build_stage_dots(TOT_STAGES)
        else:
            self.tot_badge.setText("⬡  NORMAL WORKFLOW")
            self.tot_badge.setStyleSheet(f"color:{BLUE};")
            self.active_stages = list(NORMAL_STAGES)
            self._build_stage_buttons(NORMAL_STAGES, enabled=False)
            self._build_stage_dots(NORMAL_STAGES)

    def _after_run_all(self):
        failed = getattr(self, "_run_failed", False)
        self._run_failed = False
        self.append_log("=== PIPELINE STOPPED ===" if failed else "=== PIPELINE COMPLETE ===")
        self._stop_clock()                       # freeze stage clock at its time
        self._stop_pipeline_clock(success=not failed)  # freeze pipeline clock
        self._stop_shimmer()                     # stop pulsing, keep the fill
        self._re_enable_ui()


# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = SAXWindow()
    window.populate_projects()
    window.show()
    # Auto-refresh cache in background on startup
    QTimer.singleShot(500, window.refresh_projects)
    sys.exit(app.exec())