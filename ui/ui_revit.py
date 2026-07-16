# --- SAX path bootstrap (added by migrate_to_sax) ---
import os as _sax_os, sys as _sax_sys
_sax_sys.path.insert(0, _sax_os.path.join(
    _sax_os.path.dirname(_sax_os.path.abspath(__file__)), '..', '_shared'))
# --- end bootstrap ---

"""
ui_revit.py — SAX Revit + XL integration UI  (VISUAL BASE / PROTOTYPE)
=====================================================================
This is the sibling app to ui_sax.py. It shares the look (via _shared/theme.py)
but uses a TEAL accent so it's obviously a different tool.

RIGHT NOW everything is a visual base: buttons, toggles, the member-link list,
the sync pipeline with per-stage clocks, and the running timers all work, but
the actions just log "(not wired yet)". We'll connect the real Revit/XL scripts
later.

Run:  python ui_revit.py
"""

import sys

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QTextEdit, QFrame,
    QListWidget, QListWidgetItem,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

import theme as th

ACCENT = th.ACCENT_TEAL   # <- the one difference from the setup UI

# stages shown in the sync pipeline (placeholder names for now)
PIPELINE_STAGES = [
    "Read Revit Selection",
    "Map to XL Cell",
    "Run Calcs",
    "Validate Result",
    "Push Size to Revit",
]

# placeholder members for the link list (later: pulled live)
SAMPLE_MEMBERS = [
    ("HDR-1", "4x12 DF"),
    ("HDR-2", "5.25x11.875 GLB"),
    ("BM-1",  "6x14 DF"),
    ("BM-2",  "W12x26"),
    ("POST-1", "6x6 DF"),
]


def fmt(sec):
    return f"{sec // 60:02d}:{sec % 60:02d}"


# =========================
# STAGE ROW
# =========================

class StageRow(QWidget):
    def __init__(self, name):
        super().__init__()
        self.name = name
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 4, 8, 4)

        self.dot = QLabel("●")
        self.dot.setStyleSheet(f"color:{th.SUBTEXT}; font-size:14px;")
        self.label = QLabel(name)
        self.label.setStyleSheet(f"color:{th.TEXT}; font-family:Arial; font-size:12px;")
        self.clock = QLabel("00:00")
        self.clock.setStyleSheet(f"color:{th.SUBTEXT}; font-family:Consolas; font-size:12px;")

        row.addWidget(self.dot)
        row.addWidget(self.label)
        row.addStretch()
        row.addWidget(self.clock)

    def set_state(self, state):
        colors = {"idle": th.SUBTEXT, "active": ACCENT,
                  "done": th.GREEN, "error": th.RED}
        self.dot.setStyleSheet(f"color:{colors.get(state, th.SUBTEXT)}; font-size:14px;")

    def set_seconds(self, sec):
        self.clock.setText(fmt(sec))

    def reset(self):
        self.set_state("idle")
        self.set_seconds(0)


# =========================
# MAIN WINDOW
# =========================

class RevitWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SAX — Revit + XL Sync")
        self.setMinimumSize(1000, 720)
        self.resize(1240, 760)
        self.setStyleSheet(f"background-color:{th.BG}; color:{th.TEXT};")

        # state
        self.linkage_live   = False
        self.highlight_on   = True
        self.total_seconds  = 0
        self.stage_rows     = {}
        self._run_index     = -1
        self._stage_seconds = 0

        # timers
        self.total_clock = QTimer(self); self.total_clock.timeout.connect(self._tick_total)
        self.total_clock.start(1000)
        self.stage_clock = QTimer(self); self.stage_clock.timeout.connect(self._tick_stage)
        self.stage_step  = QTimer(self); self.stage_step.timeout.connect(self._advance_stage)

        self._build_ui()
        self.log("Ready. This is the visual base — actions aren't wired to Revit/XL yet.")

    # ---------- build ----------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 12, 16, 16)
        root.setSpacing(12)

        root.addWidget(self._header())

        body = QHBoxLayout()
        body.setSpacing(12)
        body.addWidget(self._members_panel(), 5)
        body.addWidget(self._controls_panel(), 4)
        root.addLayout(body, 1)

        root.addWidget(self._log_panel(), 0)

    def _header(self):
        bar = QFrame()
        bar.setStyleSheet(th.panel_qss())
        h = QHBoxLayout(bar)
        h.setContentsMargins(16, 10, 16, 10)

        title = QLabel("SAX")
        title.setStyleSheet(th.header_title_qss(ACCENT))
        sub = QLabel("Revit + XL Sync")
        sub.setStyleSheet(f"color:{th.SUBTEXT}; font-family:Arial; font-size:13px;")
        h.addWidget(title)
        h.addWidget(sub)
        h.addStretch()

        # live-linkage status pill
        self.linkage_pill = QPushButton("LINKAGE: OFF")
        self.linkage_pill.setCheckable(True)
        self.linkage_pill.setCursor(Qt.PointingHandCursor)
        self.linkage_pill.clicked.connect(self.toggle_linkage)
        self.linkage_pill.setStyleSheet(th.toggle_style(False, ACCENT))
        h.addWidget(self.linkage_pill)

        clock_lbl = QLabel("Session")
        clock_lbl.setStyleSheet(f"color:{th.SUBTEXT}; font-family:Arial; font-size:11px;")
        self.total_label = QLabel("00:00")
        self.total_label.setStyleSheet(f"color:{th.TEXT}; font-family:Consolas; font-size:16px;")
        h.addSpacing(16)
        h.addWidget(clock_lbl)
        h.addWidget(self.total_label)
        return bar

    def _members_panel(self):
        panel = QFrame(); panel.setStyleSheet(th.panel_qss())
        v = QVBoxLayout(panel)
        v.setContentsMargins(14, 12, 14, 14)

        head = QLabel("MEMBERS")
        head.setStyleSheet(f"color:{ACCENT}; font-family:Arial; font-size:13px; font-weight:bold;")
        v.addWidget(head)
        hint = QLabel("Select a member, then link it to a Revit element and an XL calc.")
        hint.setStyleSheet(f"color:{th.SUBTEXT}; font-family:Arial; font-size:11px;")
        v.addWidget(hint)

        self.member_list = QListWidget()
        self.member_list.setStyleSheet(f"""
            QListWidget {{ background-color:{th.BG}; border:1px solid {th.BORDER};
                          border-radius:6px; color:{th.TEXT}; font-family:Arial; font-size:12px; }}
            QListWidget::item {{ padding:8px 10px; }}
            QListWidget::item:selected {{ background-color:{ACCENT}; color:#10202A; }}
        """)
        for tag, size in SAMPLE_MEMBERS:
            QListWidgetItem(f"{tag}     —     {size}     ·   (unlinked)", self.member_list)
        v.addWidget(self.member_list, 1)

        row1 = QHBoxLayout()
        for label, slot in [("+ Add Member", self.add_member),
                            ("Rename Tag", self.rename_member),
                            ("Remove", self.remove_member)]:
            b = QPushButton(label); b.setStyleSheet(th.button_base(ACCENT))
            b.clicked.connect(slot); row1.addWidget(b)
        v.addLayout(row1)

        row2 = QHBoxLayout()
        link_btn = QPushButton("Link Selected  →  Revit element")
        link_btn.setStyleSheet(th.button_accent(ACCENT))
        link_btn.clicked.connect(self.link_selected)
        xl_btn = QPushButton("Link  →  XL calc")
        xl_btn.setStyleSheet(th.button_accent(ACCENT))
        xl_btn.clicked.connect(self.link_xl)
        row2.addWidget(link_btn); row2.addWidget(xl_btn)
        v.addLayout(row2)
        return panel

    def _controls_panel(self):
        panel = QFrame(); panel.setStyleSheet(th.panel_qss())
        v = QVBoxLayout(panel)
        v.setContentsMargins(14, 12, 14, 14)
        v.setSpacing(10)

        # --- sync controls ---
        head = QLabel("SYNC CONTROLS")
        head.setStyleSheet(f"color:{ACCENT}; font-family:Arial; font-size:13px; font-weight:bold;")
        v.addWidget(head)

        self.highlight_toggle = QPushButton("Highlight XL changes: ON")
        self.highlight_toggle.setCheckable(True); self.highlight_toggle.setChecked(True)
        self.highlight_toggle.setCursor(Qt.PointingHandCursor)
        self.highlight_toggle.setStyleSheet(th.toggle_style(True, ACCENT))
        self.highlight_toggle.clicked.connect(self.toggle_highlight)
        v.addWidget(self.highlight_toggle)

        grid = QGridLayout()
        buttons = [
            ("Re-Sync Now", self.resync),
            ("Clear XL Highlights", self.clear_highlights),
            ("Add Load Values", self.add_load_values),
            ("Pull Revit Value → Text", self.pull_revit_value),
            ("Update Calc-Map Tag", self.update_tag),
            ("Push XL Size → Revit", self.push_size),
        ]
        for i, (label, slot) in enumerate(buttons):
            b = QPushButton(label); b.setStyleSheet(th.button_base(ACCENT))
            b.clicked.connect(slot)
            grid.addWidget(b, i // 2, i % 2)
        v.addLayout(grid)

        # --- pipeline ---
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color:{th.BORDER};")
        v.addWidget(sep)

        phead = QHBoxLayout()
        pl = QLabel("SYNC PIPELINE")
        pl.setStyleSheet(f"color:{ACCENT}; font-family:Arial; font-size:13px; font-weight:bold;")
        self.pipeline_total = QLabel("00:00")
        self.pipeline_total.setStyleSheet(f"color:{th.SUBTEXT}; font-family:Consolas; font-size:12px;")
        phead.addWidget(pl); phead.addStretch(); phead.addWidget(self.pipeline_total)
        v.addLayout(phead)

        for name in PIPELINE_STAGES:
            row = StageRow(name)
            self.stage_rows[name] = row
            v.addWidget(row)

        run = QPushButton("▶  Run Sync Pipeline")
        run.setStyleSheet(th.button_accent(ACCENT))
        run.clicked.connect(self.run_pipeline)
        v.addWidget(run)
        v.addStretch()
        return panel

    def _log_panel(self):
        panel = QFrame(); panel.setStyleSheet(th.panel_qss())
        panel.setFixedHeight(150)
        v = QVBoxLayout(panel); v.setContentsMargins(12, 8, 12, 10)
        head = QLabel("LOG")
        head.setStyleSheet(f"color:{th.SUBTEXT}; font-family:Arial; font-size:11px; font-weight:bold;")
        v.addWidget(head)
        self.log_box = QTextEdit(); self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet(f"""
            QTextEdit {{ background-color:{th.BG}; border:1px solid {th.BORDER};
                        border-radius:6px; color:{th.TEXT};
                        font-family:Consolas; font-size:11px; }}
        """)
        v.addWidget(self.log_box)
        return panel

    # ---------- helpers ----------
    def log(self, msg):
        self.log_box.append(f"  {msg}")

    def _selected_tag(self):
        it = self.member_list.currentItem()
        return it.text().split("—")[0].strip() if it else None

    # ---------- timers ----------
    def _tick_total(self):
        self.total_seconds += 1
        self.total_label.setText(fmt(self.total_seconds))

    def _tick_stage(self):
        self._stage_seconds += 1
        if 0 <= self._run_index < len(PIPELINE_STAGES):
            self.stage_rows[PIPELINE_STAGES[self._run_index]].set_seconds(self._stage_seconds)
        self._pipeline_seconds = getattr(self, "_pipeline_seconds", 0) + 1
        self.pipeline_total.setText(fmt(self._pipeline_seconds))

    def _advance_stage(self):
        if 0 <= self._run_index < len(PIPELINE_STAGES):
            self.stage_rows[PIPELINE_STAGES[self._run_index]].set_state("done")
        self._run_index += 1
        self._stage_seconds = 0
        if self._run_index >= len(PIPELINE_STAGES):
            self.stage_clock.stop(); self.stage_step.stop()
            self.log("Sync pipeline complete (simulated).")
            return
        self.stage_rows[PIPELINE_STAGES[self._run_index]].set_state("active")
        self.log(f"  ▸ {PIPELINE_STAGES[self._run_index]}")

    # ---------- actions (placeholders) ----------
    def toggle_linkage(self):
        self.linkage_live = not self.linkage_live
        self.linkage_pill.setChecked(self.linkage_live)
        self.linkage_pill.setText(f"LINKAGE: {'ON' if self.linkage_live else 'OFF'}")
        self.linkage_pill.setStyleSheet(th.toggle_style(self.linkage_live, ACCENT))
        state = "ON — XL⇄Revit will auto-update" if self.linkage_live else "OFF — safe to edit freely"
        self.log(f"Live linkage {state}.")

    def toggle_highlight(self):
        self.highlight_on = not self.highlight_on
        self.highlight_toggle.setChecked(self.highlight_on)
        self.highlight_toggle.setText(f"Highlight XL changes: {'ON' if self.highlight_on else 'OFF'}")
        self.highlight_toggle.setStyleSheet(th.toggle_style(self.highlight_on, ACCENT))
        self.log(f"XL change-highlighting {'ON' if self.highlight_on else 'OFF'}.")

    def add_member(self):        self.log("Add Member — (not wired yet)")
    def rename_member(self):     self.log(f"Rename tag '{self._selected_tag()}' — (not wired yet)")
    def remove_member(self):     self.log(f"Remove '{self._selected_tag()}' — (not wired yet)")
    def link_selected(self):     self.log(f"Link '{self._selected_tag()}' → pick a Revit element — (not wired yet)")
    def link_xl(self):           self.log(f"Link '{self._selected_tag()}' → pick an XL calc — (not wired yet)")
    def resync(self):            self.log("Re-Sync Now — re-run calcs & update Revit — (not wired yet)")
    def clear_highlights(self):  self.log("Clear XL Highlights — (not wired yet)")
    def add_load_values(self):   self.log("Add Load Values — pick text box, then XL cell — (not wired yet)")
    def pull_revit_value(self):  self.log("Pull Revit Value → Text box — (not wired yet)")
    def update_tag(self):        self.log("Update Calc-Map Tag → text box + XL + Revit — (not wired yet)")
    def push_size(self):         self.log("Push XL Size → Revit member — (not wired yet)")

    def run_pipeline(self):
        for name in PIPELINE_STAGES:
            self.stage_rows[name].reset()
        self._pipeline_seconds = 0
        self.pipeline_total.setText("00:00")
        self._run_index = 0
        self._stage_seconds = 0
        self.stage_rows[PIPELINE_STAGES[0]].set_state("active")
        self.log("Running sync pipeline (simulated)...")
        self.log(f"  ▸ {PIPELINE_STAGES[0]}")
        self.stage_clock.start(1000)
        self.stage_step.start(1400)   # advance a stage every ~1.4s (demo)


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Arial", 10))
    win = RevitWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
