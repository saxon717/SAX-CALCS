import os
import sys
import subprocess
import threading
import queue
import json

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QProgressBar, QDialog, QFrame,
    QCompleter, QSplashScreen
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer, QStringListModel
from PySide6.QtGui import QFont, QIntValidator, QPixmap, QColor

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

SCRIPTS = {
    "info":       "01_info.py",
    "monday":     "02_monday_contract.py",
    "apn":        "03_apn.py",
    "tot":        "04_tot.py",
    "asce":       "05_asce.py",
    "lat":        "06_lat.py",
    "vert":       "07_vert.py",
    "sync":       "08_sync.py",
    "notify":     "09_notify.py",
    "tot_asce":   "tot_asce.py",
    "tot_lat":    "tot_lat.py",
    "tot_vert":   "tot_vert.py",
    "tot_sync":   "tot_sync.py",
    "tot_notify": "tot_notify.py",
}

NORMAL_STAGES  = ["apn", "tot", "asce", "lat", "vert"]
TOT_STAGES     = ["apn", "tot", "tot_asce", "tot_lat", "tot_vert"]
DEFAULT_STAGES = NORMAL_STAGES

STAGE_LABELS = {
    "info":       "01 — Project Info",
    "monday":     "Upload Contract",
    "apn":        "02 — APN Verification",
    "tot":        "03 — TOT Check",
    "asce":       "04 — ASCE Hazard Data",
    "lat":        "05 — Lateral Calcs",
    "vert":       "06 — Vertical Calcs",
    "sync":       "07 — Sync",
    "notify":     "08 — Notify",
    "tot_asce":   "04 — TOT ASCE Hazard Data",
    "tot_lat":    "05 — TOT Lateral Calcs",
    "tot_vert":   "06 — TOT Vertical Calcs",
    "tot_sync":   "07 — TOT Sync",
    "tot_notify": "08 — TOT Notify",
}

DEPENDENCIES = {
    "apn":      ["info"],
    "tot":      ["info", "apn"],
    "asce":     ["info", "apn", "tot"],
    "lat":      ["info", "apn", "tot", "asce"],
    "vert":     ["info", "apn", "tot", "asce", "lat"],
    "tot_asce": ["info", "apn", "tot"],
    "tot_lat":  ["info", "apn", "tot", "tot_asce"],
    "tot_vert": ["info", "apn", "tot", "tot_asce", "tot_lat"],
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
                 "Finding board", "Finding project item", "Uploading file"],
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
    "tot_asce": ["Reading INFO file", "Opening ASCE website",
                 "Entering address", "Selecting criteria",
                 "Downloading report", "Saving PDF"],
    "tot_lat":  ["Reading INFO file", "Finding ASCE PDF",
                 "Copying template", "Extracting seismic values",
                 "Extracting wind values", "Writing Excel"],
    "tot_vert": ["Reading INFO file", "Finding LAT file",
                 "Copying template", "Copying cover data",
                 "Writing snow load", "Saving Excel"],
}

# =========================
# SIGNALS
# =========================

class Signals(QObject):
    log               = Signal(str)
    stage_done        = Signal(str, bool)
    pipeline_progress = Signal(int, int)
    stage_progress    = Signal(int, int)
    after_info        = Signal(bool)
    req_open_pdf      = Signal(str, str)
    req_bad_template  = Signal(str)
    req_confirm_apn   = Signal(str)
    req_confirm_tot   = Signal(str)
    req_addr_mismatch = Signal(str, str)
    req_monday_mismatch = Signal(str, str)
    req_info_exists   = Signal(str)
    req_upload_confirm  = Signal(str)   # file already on Monday — ask to re-upload
    req_xl_complete     = Signal(str)   # XL files done — pipe-delimited paths
    req_tot_manual      = Signal(str)   # TOT inconclusive or unmatched — manual Y/N


signals = Signals()

# =========================
# PROJECT CACHE
# =========================

CACHE_FILE = os.path.join(script_folder, "project_cache.json")

def scan_all_projects(progress_cb=None):
    """Scan all year folders and return list of (number, name, path) tuples."""
    projects = []
    if not os.path.exists(base_folder):
        return projects
    try:
        year_folders = [
            d for d in os.listdir(base_folder)
            if os.path.isdir(os.path.join(base_folder, d))
            and d.endswith("-XXX")
        ]
    except Exception:
        return projects

    for i, yf in enumerate(sorted(year_folders)):
        yf_path = os.path.join(base_folder, yf)
        try:
            for folder in sorted(os.listdir(yf_path)):
                full = os.path.join(yf_path, folder)
                if not os.path.isdir(full):
                    continue
                # Project folders start with XX-XXX pattern
                parts = folder.split(" ", 1)
                if len(parts) >= 1 and "-" in parts[0]:
                    number = parts[0].strip()
                    name   = parts[1].strip() if len(parts) > 1 else ""
                    projects.append({
                        "number": number,
                        "name":   name,
                        "path":   full,
                        "folder": folder,
                    })
        except Exception:
            pass
        if progress_cb:
            progress_cb(i + 1, len(year_folders))

    return projects


def load_cache():
    """Load cached project list from disk."""
    if not os.path.exists(CACHE_FILE):
        return []
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_cache(projects):
    """Save project list to disk cache."""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(projects, f, indent=2)
    except Exception:
        pass


def refresh_cache(progress_cb=None):
    """
    Load existing cache, scan for new folders not already in it,
    append them, save and return full list.
    """
    existing   = load_cache()
    known_paths = {p["path"] for p in existing}
    fresh       = scan_all_projects(progress_cb)
    new_entries = [p for p in fresh if p["path"] not in known_paths]
    combined    = existing + new_entries
    if new_entries:
        save_cache(combined)
    return combined


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
    archive_folder = os.path.join(project_root, "CALCULATIONS", "ARCHIVE")
    if not os.path.exists(archive_folder):
        return {}
    latest_time = 0
    info_path = ""
    for file in os.listdir(archive_folder):
        upper = file.upper()
        if file.endswith(".txt") and "INFO" in upper and project_number in upper:
            full_path = os.path.join(archive_folder, file)
            t = os.path.getmtime(full_path)
            if t > latest_time:
                latest_time = t
                info_path = full_path
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
# SPLASH SCREEN
# =========================

class SAXSplash(QWidget):
    done = Signal(list)   # emits project list when scan complete

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.SplashScreen | Qt.FramelessWindowHint)
        self.setFixedSize(420, 200)
        self.setStyleSheet(
            f"background-color:{BG};border:1px solid {BORDER};border-radius:10px;"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(12)

        title = QLabel("SAX")
        title.setFont(QFont("Arial", 28, QFont.Bold))
        title.setStyleSheet(f"color:{BLUE};background:transparent;border:none;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.status = QLabel("Loading projects...")
        self.status.setFont(QFont("Arial", 10))
        self.status.setStyleSheet(f"color:{SUBTEXT};background:transparent;border:none;")
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        self.bar.setStyleSheet(
            f"QProgressBar{{background:{BTN_DEFAULT};border-radius:3px;border:none;}}"
            f"QProgressBar::chunk{{background:{BLUE};border-radius:3px;}}"
        )
        layout.addWidget(self.bar)

        # Center on screen
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width()  - self.width())  // 2,
            (screen.height() - self.height()) // 2,
        )

    def start(self):
        def worker():
            def progress(current, total):
                pct = int((current / total) * 100) if total else 0
                # Use QTimer to update UI safely from thread
                QTimer.singleShot(0, lambda: self._update(pct))
            projects = refresh_cache(progress_cb=progress)
            QTimer.singleShot(0, lambda: self.done.emit(projects))

        threading.Thread(target=worker, daemon=True).start()

    def _update(self, pct):
        self.bar.setValue(pct)
        self.status.setText(f"Scanning projects... {pct}%")


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
            and len(self.b3.text()) == 3
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
        no_btn = QPushButton("No — Go Back")
        no_btn.setStyleSheet(DIALOG_BTN_GRAY)
        no_btn.clicked.connect(self.reject)
        yes_btn = QPushButton("Yes — Run Info")
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
        no_btn = QPushButton("No — Continue")
        no_btn.setStyleSheet(DIALOG_BTN_GRAY)
        no_btn.clicked.connect(self.reject)
        yes_btn = QPushButton("Yes — Open PDF")
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
        self.main_layout.addWidget(
            self._title_label(
                f"{len(files)} INFO file(s) found for this project."
            )
        )
        self.main_layout.addWidget(
            self._body_label("What would you like to do?")
        )
        for f in files:
            try:
                modified = os.path.getmtime(f)
                date_str = datetime.fromtimestamp(modified).strftime(
                    "%m/%d/%y %I:%M %p"
                )
                label = f"{os.path.basename(f)}  —  {date_str}"
            except Exception:
                label = os.path.basename(f)
            self.main_layout.addWidget(self._info_box("FILE", label))

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addStretch()
        skip_btn = QPushButton("Skip")
        skip_btn.setStyleSheet(DIALOG_BTN_BLUE)
        skip_btn.clicked.connect(lambda: self.done(3))
        overwrite_btn = QPushButton("Overwrite Most Recent")
        overwrite_btn.setStyleSheet(DIALOG_BTN_RED)
        overwrite_btn.clicked.connect(lambda: self.done(2))
        new_btn = QPushButton("Create New")
        new_btn.setStyleSheet(DIALOG_BTN_GREEN)
        new_btn.clicked.connect(self.accept)
        new_btn.setDefault(True)
        row.addWidget(skip_btn)
        row.addWidget(overwrite_btn)
        row.addWidget(new_btn)
        self.main_layout.addLayout(row)


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
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(DIALOG_BTN_GRAY)
        cancel_btn.clicked.connect(self.reject)
        confirm_btn = QPushButton("Confirm Address")
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
    def __init__(self, parent, current_apn, contract_pdf=""):
        super().__init__(parent, "Verify APN")
        self._contract_pdf = contract_pdf
        self.result_apn = current_apn
        self.main_layout.addWidget(self._title_label("Verify the APN."))
        self.main_layout.addWidget(
            self._info_box("APN FROM INFO FILE", current_apn)
        )
        self.main_layout.addWidget(
            self._body_label(
                "If correct, click Confirm. "
                "If not, edit the boxes below."
            )
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
        open_btn = QPushButton("Open Contract PDF")
        open_btn.setStyleSheet(DIALOG_BTN_GRAY)
        open_btn.clicked.connect(self._open_pdf)
        self.main_layout.addWidget(open_btn)
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(DIALOG_BTN_GRAY)
        cancel_btn.clicked.connect(self.reject)
        confirm_btn = QPushButton("Confirm APN")
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
                "APN must be XXX-XXX-XXX with 3 digits each."
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
        no_btn = QPushButton("No — Keep Existing")
        no_btn.setStyleSheet(DIALOG_BTN_GRAY)
        no_btn.clicked.connect(self.reject)
        yes_btn = QPushButton("Yes — Update")
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
        override_btn = QPushButton("Override Status")
        override_btn.setStyleSheet(DIALOG_BTN_RED)
        override_btn.clicked.connect(lambda: self.done(2))
        confirm_btn = QPushButton("Confirm")
        confirm_btn.setStyleSheet(DIALOG_BTN_BLUE)
        confirm_btn.clicked.connect(self.accept)
        confirm_btn.setDefault(True)
        row.addWidget(override_btn)
        row.addWidget(confirm_btn)
        self.main_layout.addLayout(row)


class UploadConfirmDialog(SAXDialog):
    """Shown only when the file already exists on Monday — ask to re-upload."""
    def __init__(self, parent, contract_name):
        super().__init__(parent, "File Already on Monday")
        self.main_layout.addWidget(
            self._title_label("This file already exists on Monday.com.")
        )
        self.main_layout.addWidget(
            self._info_box("CONTRACT FILE", contract_name)
        )
        self.main_layout.addWidget(
            self._body_label(
                "The contract was already found on Monday. "
                "Upload it again anyway?"
            )
        )
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch()
        skip_btn = QPushButton("Skip")
        skip_btn.setStyleSheet(DIALOG_BTN_GRAY)
        skip_btn.clicked.connect(lambda: self.done(2))
        upload_btn = QPushButton("Yes — Upload Again")
        upload_btn.setStyleSheet(DIALOG_BTN_BLUE)
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
        no_btn = QPushButton("No — Cancel")
        no_btn.setStyleSheet(DIALOG_BTN_GRAY)
        no_btn.clicked.connect(self.reject)
        yes_btn = QPushButton("Yes — Use This")
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
        cancel_btn = QPushButton("Cancel")
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
# TOT MANUAL DIALOG
# =========================

class TOTManualDialog(SAXDialog):
    def __init__(self, parent, message):
        super().__init__(parent, "TOT Manual Override")
        self.main_layout.addWidget(
            self._title_label("Manual Override Required")
        )
        self.main_layout.addWidget(
            self._body_label(message)
        )
        self.main_layout.addWidget(
            self._body_label("Is this a TOT project?")
        )
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch()
        no_btn = QPushButton("No — Not TOT")
        no_btn.setStyleSheet(DIALOG_BTN_BLUE)
        no_btn.clicked.connect(self.reject)
        yes_btn = QPushButton("Yes — TOT Project")
        yes_btn.setStyleSheet(DIALOG_BTN_GREEN)
        yes_btn.clicked.connect(self.accept)
        yes_btn.setDefault(True)
        row.addWidget(no_btn)
        row.addWidget(yes_btn)
        self.main_layout.addLayout(row)


# =========================
# XL COMPLETE DIALOG
# =========================

class XLCompleteDialog(SAXDialog):
    def __init__(self, parent, paths):
        super().__init__(parent, "XL Files Created")
        self.paths      = paths        # list of file paths
        self.keep_open  = []           # paths user wants to keep open

        self.main_layout.addWidget(
            self._title_label("XL files created successfully.")
        )
        self.main_layout.addWidget(
            self._body_label("Leave open for review?")
        )

        self.checkboxes = []
        for path in paths:
            cb = __import__('PySide6.QtWidgets', fromlist=['QCheckBox']).QCheckBox(
                os.path.basename(path)
            )
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

        self.no_btn = QPushButton("No — Close")
        self.no_btn.setStyleSheet(DIALOG_BTN_RED)
        self.no_btn.clicked.connect(self.reject)

        self.yes_btn = QPushButton("Yes — Leave Open")
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
        self.run_btn.setMinimumHeight(42)
        self.arrow_btn.setMinimumHeight(42)
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
        self._proc         = None
        self._stopped      = False
        self._result_queue = queue.Queue()
        self._xl_paths     = []

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
        try:
            return self._result_queue.get(timeout=timeout)
        except Exception:
            signals.log.emit(
                "ERROR: Dialog timed out — pipeline stopped."
            )
            self._proc.terminate()
            signals.stage_done.emit(key, False)
            return None

    def run(self, key, project_number):
        self._stopped = False
        path = os.path.join(script_folder, SCRIPTS.get(key, ""))

        if not os.path.exists(path):
            signals.log.emit(f"ERROR: Script not found: {path}")
            signals.stage_done.emit(key, False)
            return False

        steps      = SCRIPT_STEPS.get(key, [])
        total      = len(steps)
        step_index = [0]

        try:
            self._proc = subprocess.Popen(
                [sys.executable, "-u", path, project_number],
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

            # ── TOT MANUAL OVERRIDE (inconclusive or unmatched search) ──
            if line.startswith("UI_TOT_MANUAL:"):
                msg = line.replace("UI_TOT_MANUAL:", "").strip()
                signals.req_tot_manual.emit(msg)
                result = self._wait_for_result(key, timeout=300)
                if result is None:
                    return False
                self._proc.stdin.write(result + "\n")
                self._proc.stdin.flush()
                continue

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

        # If XL files were created, show popup and send response
        # BEFORE emitting stage_done (subprocess still waiting on stdin)
        if self._xl_paths:
            paths_str = "|".join(self._xl_paths)
            self._xl_paths = []
            signals.req_xl_complete.emit(paths_str)
            result = self._wait_for_result(key, timeout=300)
            if self._proc.poll() is None:
                self._proc.stdin.write((result or "CLOSE") + "\n")
                self._proc.stdin.flush()

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

        # Connect all signals to main thread handlers
        signals.log.connect(self.append_log)
        signals.stage_done.connect(self.on_stage_done)
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
        signals.req_tot_manual.connect(self.handle_tot_manual)

        self._build_ui()
        self._build_stage_buttons(DEFAULT_STAGES, enabled=False)

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
        dlg = APNDialog(self, current_apn, contract_pdf)
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
        files = files_str.split("|")
        dlg = InfoExistsDialog(self, files)
        result = dlg.exec()
        if result == 3:
            runner.put_result("SKIP")
        elif result == 2:
            runner.put_result("OVERWRITE")
        else:
            runner.put_result("NEW")

    def handle_xl_complete(self, paths_str):
        paths  = [p for p in paths_str.split("|") if p.strip()]
        dlg    = XLCompleteDialog(self, paths)
        result = dlg.exec()
        if result == QDialog.Accepted:
            self.append_log(
                f"XL files left open: "
                f"{', '.join(os.path.basename(p) for p in dlg.keep_open)}"
            )
            runner.put_result("KEEP")
        else:
            self.append_log("XL files closed.")
            runner.put_result("CLOSE")

    def handle_upload_confirm(self, contract_name):
        """File already on Monday — ask whether to re-upload."""
        dlg = UploadConfirmDialog(self, contract_name)
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

        subtitle = QLabel("Structural Automation Extension")
        subtitle.setFont(QFont("Arial", 9))
        subtitle.setStyleSheet(f"color:{SUBTEXT};")
        subtitle.setWordWrap(True)
        ll.addWidget(subtitle)
        ll.addSpacing(14)

        self._slabel(ll, "PROJECT")
        self.project_input = QLineEdit()
        self.project_input.setPlaceholderText("Type to search projects...")
        self.project_input.setStyleSheet(
            f"QLineEdit{{background-color:{BG};color:{TEXT};"
            f"border:1px solid {BORDER};border-radius:6px;"
            f"padding:8px 10px;font-family:Arial;font-size:13px;}}"
            f"QLineEdit:focus{{border-color:{BLUE};}}"
        )
        self.project_input.returnPressed.connect(self.load_project)
        self._completer_model = QStringListModel()
        self._completer = QCompleter()
        self._completer.setModel(self._completer_model)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchContains)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self._completer.popup().setStyleSheet(
            f"QListView{{background:{PANEL};color:{TEXT};border:1px solid {BORDER};"
            f"font-family:Arial;font-size:12px;padding:4px;}}"
            f"QListView::item:selected{{background:{BLUE};color:white;}}"
        )
        self._completer.activated.connect(self._on_project_selected)
        self.project_input.setCompleter(self._completer)
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

        self.load_btn = QPushButton("Select Project")
        self.load_btn.setStyleSheet(
            f"QPushButton{{background-color:{BTN_DEFAULT};color:{TEXT};"
            f"border:1px solid {BORDER};border-radius:6px;padding:8px;"
            f"font-family:Arial;font-size:12px;}}"
            f"QPushButton:hover{{background-color:{BTN_HOVER};"
            f"border-color:{BLUE};}}"
        )
        self.load_btn.clicked.connect(self.load_project)
        ll.addWidget(self.load_btn)
        ll.addSpacing(6)

        self.upload_btn = QPushButton("▶▶  UPLOAD CONTRACT")
        self.upload_btn.setMinimumHeight(42)
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

        self.setup_calcs_btn = SplitButton("SETUP CALCS")
        self.setup_calcs_btn.set_enabled(False)
        self.setup_calcs_btn.run_clicked.connect(self.run_all)
        self.setup_calcs_btn.arrow_clicked.connect(
            self._toggle_calcs_stages
        )
        ll.addWidget(self.setup_calcs_btn)

        self.stages_container = QWidget()
        self.stages_container.setVisible(False)
        self.stages_container.setStyleSheet("background:transparent;")
        self.stages_layout = QVBoxLayout(self.stages_container)
        self.stages_layout.setContentsMargins(0, 2, 0, 2)
        self.stages_layout.setSpacing(4)
        ll.addWidget(self.stages_container)

        self.setup_revit_btn = QPushButton("▶▶  SETUP REVIT")
        self.setup_revit_btn.setMinimumHeight(42)
        self.setup_revit_btn.setStyleSheet(
            f"QPushButton{{background-color:{PANEL};color:#555577;"
            f"border:1px solid #333355;border-radius:8px;padding:11px 16px;"
            f"font-family:Arial;font-size:13px;font-weight:bold;text-align:left;}}"
        )
        self.setup_revit_btn.setEnabled(False)
        ll.addWidget(self.setup_revit_btn)

        ll.addStretch()
        root.addWidget(left)

        # RIGHT PANEL
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(20, 20, 20, 16)
        rl.setSpacing(8)

        # Pipeline bar
        ph = QHBoxLayout()
        pl = QLabel("PIPELINE PROGRESS")
        pl.setFont(QFont("Arial", 8, QFont.Bold))
        pl.setStyleSheet(f"color:{SUBTEXT};letter-spacing:1px;")
        ph.addWidget(pl)
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

        # Stage bar
        sh = QHBoxLayout()
        sl = QLabel("CURRENT STAGE")
        sl.setFont(QFont("Arial", 8, QFont.Bold))
        sl.setStyleSheet(f"color:{SUBTEXT};letter-spacing:1px;")
        sh.addWidget(sl)
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
            f"padding:12px;font-family:Courier New;font-size:11px;}}"
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
        self.stop_btn.setEnabled(False)
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

    def _toggle_calcs_stages(self):
        self._calcs_expanded = not self._calcs_expanded
        self.stages_container.setVisible(self._calcs_expanded)

    def _build_stage_buttons(self, stages, enabled=True):
        for i in reversed(range(self.stages_layout.count())):
            w = self.stages_layout.itemAt(i).widget()
            if w:
                w.deleteLater()
        self.stage_buttons = {}
        for key in stages:
            btn = StageButton(key)
            if key not in COMING_SOON:
                btn.clicked.connect(
                    lambda checked, k=key: self.run_single(k)
                )
                if enabled:
                    btn.set_enabled_active(True)
            self.stages_layout.addWidget(btn)
            self.stage_buttons[key] = btn

    def _re_enable_ui(self):
        self.stop_btn.setEnabled(False)
        self.load_btn.setEnabled(True)
        self._stop_clock()
        if not self.running:
            self.setup_calcs_btn.set_enabled(True)
            self.upload_btn.setEnabled(True)
            for btn in self.stage_buttons.values():
                if btn.key not in COMING_SOON:
                    btn.set_enabled_active(True)

    # =========================
    # LOAD PROJECT
    # =========================

    def populate_projects(self, projects):
        """Called after splash scan — loads projects into completer."""
        self._project_cache = {
            p["number"]: p for p in projects
        }
        # Build display strings: "26-035 — Project Name"
        display = [
            f"{p['number']} — {p['name']}" if p['name'] else p['number']
            for p in sorted(projects, key=lambda x: x['number'], reverse=True)
        ]
        self._completer_model.setStringList(display)
        self.append_log(f"  ▸ {len(projects)} projects loaded")

    def _on_project_selected(self, text):
        """User picked a project from the dropdown."""
        # Extract just the number from "26-035 — Name"
        number = text.split(" — ")[0].strip()
        self.project_input.setText(number)

    def load_project(self):
        pn = self.project_input.text().strip()
        if not pn:
            self.append_log("ERROR: Enter a project number.")
            return
        project_root, project_name = find_project(pn)
        if not project_root:
            self.project_name_label.setText("Project not found.")
            self.project_name_label.setStyleSheet(f"color:{RED};")
            self.append_log(f"ERROR: No project found for {pn}")
            return

        dlg = ConfirmProjectDialog(self, project_name)
        if dlg.exec() != QDialog.Accepted:
            self.append_log("Project load cancelled.")
            return

        self.project_number   = pn
        self.project_root     = project_root
        self.project_name     = project_name
        self.completed_stages = set()
        self.project_name_label.setText(project_name)
        self.project_name_label.setStyleSheet(f"color:{GREEN};")
        self.append_log(f"Project confirmed: {project_name}")
        self.append_log("--- Running 01 — Project Info ---")
        self.load_btn.setEnabled(False)
        self.setup_calcs_btn.set_enabled(False)
        self.upload_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._reset_stage_bars()

        def run_info():
            success = runner.run("info", pn)
            if success:
                self.completed_stages.add("info")
            signals.after_info.emit(success)

        threading.Thread(target=run_info, daemon=True).start()

    def _after_info(self, success):
        self.stop_btn.setEnabled(False)
        self.load_btn.setEnabled(True)
        if not success:
            self.append_log("ERROR: INFO stage failed.")
        self._finish_load()

    def _finish_load(self):
        self.stop_btn.setEnabled(False)
        info_data = get_info_data(self.project_root, self.project_number)
        tot = info_data.get("TOT", "").strip()
        self.tot_status = tot
        if tot == "Y":
            self.tot_badge.setText("⬡  TOT WORKFLOW")
            self.tot_badge.setStyleSheet(f"color:{YELLOW};")
            self.append_log("TOT: Y — TOT workflow loaded")
            self.active_stages = list(TOT_STAGES)
            self._build_stage_buttons(TOT_STAGES, enabled=True)
        elif tot == "N":
            self.tot_badge.setText("⬡  NORMAL WORKFLOW")
            self.tot_badge.setStyleSheet(f"color:{BLUE};")
            self.append_log("TOT: N — Normal workflow loaded")
            self.active_stages = list(NORMAL_STAGES)
            self._build_stage_buttons(NORMAL_STAGES, enabled=True)
        else:
            self.tot_badge.setText("⬡  TOT unknown — run APN & TOT first")
            self.tot_badge.setStyleSheet(f"color:{SUBTEXT};")
            self.append_log("TOT not yet determined.")
            self.active_stages = ["apn", "tot"]
            self._build_stage_buttons(["apn", "tot"], enabled=True)
        self._reset_stage_bars()
        self.setup_calcs_btn.set_enabled(True)
        self.upload_btn.setEnabled(True)

    # =========================
    # PROGRESS & CLOCK
    # =========================

    def _reset_stage_bars(self):
        self.stage_bar.setValue(0)
        self._stage_target = 0
        self.stage_step_label.setText("—")
        self.stage_bar.setStyleSheet(self._bar_style(GREEN, radius=4))
        self._start_clock()

    def _start_clock(self):
        self._stage_seconds = 0
        self.stage_timer_label.setText("00:00")
        self.stage_timer_label.setStyleSheet(f"color:{BLUE};")
        if not self._stage_clock.isActive():
            self._stage_clock.start(1000)

    def _stop_clock(self):
        self._stage_clock.stop()
        self.stage_timer_label.setStyleSheet(f"color:{SUBTEXT};")

    def _tick_clock(self):
        self._stage_seconds += 1
        mins = self._stage_seconds // 60
        secs = self._stage_seconds % 60
        self.stage_timer_label.setText(f"{mins:02d}:{secs:02d}")

    def set_pipeline_progress(self, current, total):
        if total == 0:
            return
        pct = int((current / total) * 100)
        self.pipeline_bar.setValue(pct)
        self.pipeline_pct_label.setText(f"{current} / {total} stages")
        if current == total:
            self.pipeline_bar.setStyleSheet(
                self._bar_style(GREEN, radius=6)
            )

    def set_stage_progress(self, step, total):
        if total == 0:
            return
        self._stage_target = int((step / total) * 100)
        self.stage_step_label.setText(f"Step {step} / {total}")
        if not self._stage_anim.isActive():
            self._stage_anim.start(20)
        if step == total:
            self.stage_bar.setStyleSheet(
                self._bar_style(GREEN, radius=4)
            )

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
        if any(w in message for w in ["ERROR", "FAILED", "EXCEPTION"]):
            color = RED
        elif any(w in message for w in [
            "SUCCESS", "COMPLETE", "DONE",
            "UPLOADED", "FOUND", "CREATED", "SAVED"
        ]):
            color = GREEN
        elif any(w in message for w in ["WARNING", "WARN", "MISMATCH"]):
            color = YELLOW
        elif message.startswith("  ▸"):
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

    def run_single(self, key):
        if not self.project_number:
            self.append_log("ERROR: No project loaded.")
            return
        if key in COMING_SOON:
            return

        ok, missing = self._check_dependencies(key)
        if not ok:
            missing_label = STAGE_LABELS.get(missing, missing)
            stage_label   = STAGE_LABELS.get(key, key)
            dlg = DependencyDialog(self, stage_label, missing_label)
            if dlg.exec() != QDialog.Accepted:
                return

            def run_dep_then(m=missing, k=key):
                dep_btn = self.stage_buttons.get(m)
                if dep_btn:
                    dep_btn.set_running()
                signals.log.emit(
                    f"--- Running {STAGE_LABELS.get(m, m)} first ---"
                )
                self._reset_stage_bars()
                suc = runner.run(m, self.project_number)
                if suc:
                    self.completed_stages.add(m)
                    tgt = self.stage_buttons.get(k)
                    if tgt:
                        tgt.set_running()
                    signals.log.emit(
                        f"--- Now running {STAGE_LABELS.get(k, k)} ---"
                    )
                    self._reset_stage_bars()
                    runner.run(k, self.project_number)
                else:
                    signals.log.emit(
                        f"ERROR: {STAGE_LABELS.get(m, m)} failed."
                    )

            self.stop_btn.setEnabled(True)
            btn = self.stage_buttons.get(key)
            if btn:
                btn.set_running()
            threading.Thread(
                target=run_dep_then, daemon=True
            ).start()
            return

        btn = self.stage_buttons.get(key)
        if btn:
            btn.set_running()
        self.append_log(
            f"--- Running {STAGE_LABELS.get(key, key)} ---"
        )
        self._reset_stage_bars()
        self.stop_btn.setEnabled(True)

        def worker():
            runner.run(key, self.project_number)

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
        self.setup_calcs_btn.set_enabled(False)
        self.stop_btn.setEnabled(True)
        self.pipeline_bar.setStyleSheet(self._bar_style(BLUE, radius=6))
        self.pipeline_bar.setValue(0)
        self.append_log(f"=== SETUP CALCS — {total} stages ===")

        def worker():
            completed = 0
            for key in stages:
                if not self.running:
                    break
                if key in COMING_SOON:
                    completed += 1
                    signals.pipeline_progress.emit(completed, total)
                    continue
                btn = self.stage_buttons.get(key)
                if btn:
                    btn.set_running()
                signals.log.emit(
                    f"--- Running {STAGE_LABELS.get(key, key)} ---"
                )
                self._reset_stage_bars()
                success = runner.run(key, self.project_number)
                completed += 1
                signals.pipeline_progress.emit(completed, total)
                if not success:
                    signals.log.emit(
                        f"PIPELINE STOPPED — "
                        f"{STAGE_LABELS.get(key, key)} failed."
                    )
                    break
            self.running = False
            QTimer.singleShot(0, self._after_run_all)

        threading.Thread(target=worker, daemon=True).start()

    def _after_run_all(self):
        self._re_enable_ui()
        self.append_log("=== SETUP CALCS COMPLETE ===")


# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = SAXWindow()

    splash = SAXSplash()
    splash.show()
    app.processEvents()

    def on_scan_done(projects):
        window.populate_projects(projects)
        splash.close()
        window.show()

    splash.done.connect(on_scan_done)
    splash.start()

    sys.exit(app.exec())