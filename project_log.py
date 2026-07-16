"""
NOTE ON PROJECT SPECIFICITY:
    Each project gets its own log file at:
        [project_root]/UI/[project_number] LOG.txt
    
    When a new project is loaded in the UI, create a new ProjectLog 
    instance with the new project_root and project_number. The old 
    project log stays untouched. Each log is appended to — never 
    overwritten — so the full history of all runs is preserved.

project_log.py — Project Run Logger for SAX
============================================
Standalone module. Import and use in any script.
Eventually will be integrated into config.py.

Usage:
    from project_log import ProjectLog
    log = ProjectLog(project_root, project_number)
    log.start_pipeline("SETUP CALCS")
    log.stage_complete("APN Verification", skipped=True)
    log.stage_complete("TOT Lateral Calcs", warnings=1)
    log.stage_failed("TOT Seismic Data", reason="PDF save error")
    log.end_pipeline(files=["TOT LAT XL - 7.9.26.xlsm"])
"""

import os
from datetime import datetime


# =========================
# HELPERS
# =========================

def _ts():
    """Return current timestamp string."""
    return datetime.now().strftime("%m/%d/%y %I:%M %p")

def _ts_full():
    """Return full timestamp for pipeline header."""
    return datetime.now().strftime("%m/%d/%y %I:%M:%S %p")


# =========================
# PROJECT LOG CLASS
# =========================

class ProjectLog:
    def __init__(self, project_root, project_number):
        self.project_root   = project_root
        self.project_number = project_number
        self.log_path       = self._get_log_path()
        self._errors        = 0
        self._warnings      = 0
        self._stages        = []
        self._pipeline_name = ""
        self._start_time    = None

    def _get_log_path(self):
        """Log file lives in UI folder alongside INFO file."""
        ui_folder = os.path.join(self.project_root, "UI")
        os.makedirs(ui_folder, exist_ok=True)
        return os.path.join(ui_folder, f"{self.project_number} LOG.txt")

    def _write(self, line):
        """Append a line to the log file."""
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception as e:
            print(f"LOG WRITE ERROR: {e}")

    def _elapsed(self):
        """Return elapsed time since pipeline start."""
        if not self._start_time:
            return ""
        delta   = datetime.now() - self._start_time
        minutes = int(delta.total_seconds() // 60)
        seconds = int(delta.total_seconds() % 60)
        return f"{minutes:02d}:{seconds:02d}"

    # =========================
    # PIPELINE
    # =========================

    def start_pipeline(self, pipeline_name="SETUP CALCS"):
        """Call at the start of any pipeline run."""
        self._pipeline_name = pipeline_name
        self._start_time    = datetime.now()
        self._errors        = 0
        self._warnings      = 0
        self._stages        = []
        self._write("")
        self._write("=" * 60)
        self._write(f"[{_ts_full()}] === {pipeline_name} ===")
        self._write("=" * 60)

    def end_pipeline(self, files=None):
        """Call at the end of a pipeline run."""
        elapsed = self._elapsed()
        summary = f"COMPLETE in {elapsed} — {self._errors} error(s), {self._warnings} warning(s)"
        self._write(f"[{_ts()}] === {summary} ===")
        if files:
            for f in files:
                self._write(f"[{_ts()}]   📄 {f}")
        self._write("")

    def pipeline_stopped(self, reason=""):
        """Call if pipeline stopped early."""
        elapsed = self._elapsed()
        msg = f"STOPPED after {elapsed}"
        if reason:
            msg += f" — {reason}"
        self._write(f"[{_ts()}] ⛔ {msg}")
        self._write("")

    # =========================
    # STAGES
    # =========================

    def stage_complete(self, stage_name, skipped=False, warnings=0):
        """Log a stage that completed successfully."""
        self._warnings += warnings
        self._stages.append(stage_name)
        if skipped:
            self._write(f"[{_ts()}]   ↩  {stage_name} — skipped (already done)")
        elif warnings:
            self._write(f"[{_ts()}]   ⚠  {stage_name} — complete ({warnings} warning(s))")
        else:
            self._write(f"[{_ts()}]   ✓  {stage_name} — complete")

    def stage_failed(self, stage_name, reason=""):
        """Log a stage that failed."""
        self._errors += 1
        self._stages.append(stage_name)
        msg = f"[{_ts()}]   ✗  {stage_name} — FAILED"
        if reason:
            msg += f": {reason}"
        self._write(msg)

    def stage_warning(self, stage_name, message=""):
        """Log a warning within a stage."""
        self._warnings += 1
        msg = f"[{_ts()}]     ⚠  WARNING"
        if message:
            msg += f": {message}"
        self._write(msg)

    def note(self, message):
        """Log a freeform note."""
        self._write(f"[{_ts()}]     → {message}")


# =========================
# STANDALONE TEST
# =========================

if __name__ == "__main__":
    # Mock test — run this file directly to see output
    import tempfile

    test_root = tempfile.mkdtemp()
    log = ProjectLog(test_root, "26-040")

    log.start_pipeline("SETUP CALCS")
    log.stage_complete("APN Verification", skipped=True)
    log.stage_complete("TOT Verification", skipped=True)
    log.stage_complete("TOT Location Map", skipped=True)
    log.stage_complete("TOT Seismic Data")
    log.stage_complete("TOT Lateral Calcs", warnings=1)
    log.stage_warning("TOT Lateral Calcs", "Seismic Criteria I2 write failed")
    log.stage_complete("TOT Vertical Calcs")
    log.end_pipeline(files=[
        "26-040 Qiu Deck - TOT LAT XL - 7.9.26.xlsm",
        "26-040 Qiu Deck - TOT VERT XL - 7.9.26.xlsm"
    ])

    # Print the log
    with open(log.log_path) as f:
        print(f.read())