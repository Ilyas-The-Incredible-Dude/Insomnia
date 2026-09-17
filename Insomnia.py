import sys
import os
import time
import csv
import json
import fnmatch
from collections import deque
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QTableWidget, QTableWidgetItem,
                             QLabel, QHeaderView, QPushButton, QAbstractItemView,
                             QFileDialog, QTextEdit, QLineEdit, QComboBox,
                             QSystemTrayIcon, QMenu, QToolButton, QFrame,
                             QMessageBox, QCheckBox, QStyle)
from PyQt6.QtCore import QTimer, QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont, QColor, QIcon, QAction, QCursor
import psutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# =====================================================================
# THEME — matches the OmniSight brand: black background, red accents
# =====================================================================

DARK_QSS = """
QMainWindow, QWidget { background-color: #0b0c0f; color: #f4f2f0; }
QLabel { color: #f4f2f0; }
QLabel#muted { color: #8f8f9a; }
QLabel#brand { color: #ff3742; font-weight: 700; }

QLineEdit, QComboBox {
    background-color: #121318;
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 6px;
    padding: 6px 10px;
    color: #f4f2f0;
}
QLineEdit:focus, QComboBox:focus { border: 1px solid #e5121f; }
QComboBox QAbstractItemView {
    background-color: #121318; color: #f4f2f0;
    selection-background-color: #e5121f;
}

QTableWidget {
    background-color: #0e0f13;
    alternate-background-color: #121318;
    border: 1px solid rgba(255,255,255,0.10);
    gridline-color: rgba(255,255,255,0.06);
    color: #f4f2f0;
    border-radius: 8px;
    padding: 4px;
}
QHeaderView::section {
    background-color: #121318;
    color: #8f8f9a;
    padding: 8px;
    font-weight: 600;
    border: none;
    border-bottom: 2px solid #e5121f;
}
QTableWidget::item:selected { background-color: rgba(229,18,31,0.35); }

QTextEdit {
    background-color: #121318;
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 6px;
    padding: 8px;
    color: #f4f2f0;
}

QPushButton {
    background-color: #121318;
    border: 1px solid rgba(255,255,255,0.16);
    border-radius: 6px;
    padding: 7px 14px;
    color: #f4f2f0;
    font-weight: 600;
}
QPushButton:hover { border: 1px solid #e5121f; background-color: rgba(229,18,31,0.12); }
QPushButton:checked { background-color: #e5121f; border: 1px solid #e5121f; color: white; }

QPushButton#primary { background-color: #e5121f; border: 1px solid #e5121f; color: white; }
QPushButton#primary:hover { background-color: #ff3742; }
QPushButton#danger { background-color: #2a0d10; border: 1px solid #7a0a12; color: #ff8a90; }
QPushButton#danger:hover { background-color: #3a0f14; }

QFrame#alertBar {
    background-color: #7a0a12;
    border-radius: 6px;
}
QFrame#statCard {
    background-color: #121318;
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 8px;
}
QCheckBox { color: #f4f2f0; }
"""

LIGHT_QSS = ""  # falls back to native/light style when unchecked

# =====================================================================
# 1. BACKGROUND TELEMETRY ENGINE
# =====================================================================

class FileWatchHandler(FileSystemEventHandler):
    def __init__(self, signal, exclude_patterns):
        super().__init__()
        self.signal = signal
        self.exclude_patterns = exclude_patterns

    def _is_excluded(self, path):
        for pattern in self.exclude_patterns:
            if pattern and fnmatch.fnmatch(path, pattern):
                return True
        return False

    def on_any_event(self, event):
        if event.is_directory:
            return
        if self._is_excluded(event.src_path):
            return

        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        event_type = event.event_type.upper()
        src = os.path.basename(event.src_path)

        details = f"Path: {event.src_path}"
        if event_type == "MOVED":
            details = f"Moved/Renamed to: {os.path.basename(event.dest_path)}"

        self.signal.emit(timestamp, "FILESYSTEM", event_type, src, details)


class TelemetryWorker(QThread):
    log_signal = pyqtSignal(str, str, str, str, str)

    def __init__(self, watch_path, exclude_patterns):
        super().__init__()
        self.watch_path = watch_path
        self.exclude_patterns = exclude_patterns
        self.paused = False

    def set_paused(self, paused):
        self.paused = paused

    def run(self):
        self.observer = Observer()
        handler = FileWatchHandler(self.log_signal, self.exclude_patterns)
        self.observer.schedule(handler, path=self.watch_path, recursive=True)
        self.observer.start()

        known_pids = set(psutil.pids())

        while self.isRunning():
            if self.paused:
                time.sleep(0.2)
                continue

            current_pids = set(psutil.pids())
            new_pids = current_pids - known_pids

            for pid in new_pids:
                try:
                    proc = psutil.Process(pid)
                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    cmd = " ".join(proc.cmdline()[:2])
                    self.log_signal.emit(
                        timestamp,
                        "PROCESS",
                        "SPAWN",
                        proc.name(),
                        f"PID: {pid} | Cmd: {cmd}"
                    )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            known_pids = current_pids
            time.sleep(0.1)

    def stop(self):
        if hasattr(self, 'observer'):
            self.observer.stop()
            self.observer.join()
        self.terminate()

# =====================================================================
# 2. MAIN PANEL
# =====================================================================

ACTION_COLORS = {
    "DELETED":  "#ff3742",
    "CREATED":  "#3ddc84",
    "MODIFIED": "#f4c542",
    "MOVED":    "#f4c542",
    "SPAWN":    "#4aa3ff",
}
ACTION_ICONS = {
    "DELETED": "🗑️", "CREATED": "🆕", "MODIFIED": "📝",
    "MOVED": "📝", "SPAWN": "🚀",
}

# how many deletions inside this many seconds counts as a "mass delete" pattern
RANSOM_WINDOW_SECS = 5
RANSOM_THRESHOLD = 15


class TelemetryPanel(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OmniSight — Micro-Telemetry Flight Recorder")
        self.resize(1200, 800)

        self.watch_path = os.path.expanduser("~")
        self.exclude_patterns = ["*/.git/*", "*/node_modules/*", "*/__pycache__/*"]
        self.dark_mode = True
        self.all_rows = []          # full unfiltered history, newest first
        self.event_count = 0
        self.delete_timestamps = deque()
        self.sound_alerts = True

        self.apply_theme()
        self.init_ui()
        self.init_tray()
        self.start_worker()

    # ---------------- theme ----------------
    def apply_theme(self):
        QApplication.instance().setStyleSheet(DARK_QSS if self.dark_mode else LIGHT_QSS)

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.apply_theme()

    # ---------------- worker lifecycle ----------------
    def start_worker(self):
        self.worker = TelemetryWorker(self.watch_path, self.exclude_patterns)
        self.worker.log_signal.connect(self.append_log_row)
        self.worker.start()

    def restart_worker(self):
        self.worker.stop()
        self.start_worker()

    # ---------------- UI ----------------
    def init_ui(self):
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # ─── HEADER ──────────────────────────────────────────────
        header = QHBoxLayout()
        brand = QLabel("● OmniSight")
        brand.setObjectName("brand")
        brand.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header.addWidget(brand)

        self.spinner_lbl = QLabel("⠋")
        self.spinner_lbl.setFont(QFont("Consolas", 12))
        self.last_action_lbl = QLabel("Monitoring…")
        self.last_action_lbl.setObjectName("muted")
        header.addSpacing(20)
        header.addWidget(self.spinner_lbl)
        header.addWidget(self.last_action_lbl)
        header.addStretch()

        self.theme_btn = QPushButton("☀ / ☾")
        self.theme_btn.setFixedWidth(60)
        self.theme_btn.clicked.connect(self.toggle_theme)
        header.addWidget(self.theme_btn)
        layout.addLayout(header)

        # ─── STAT CARDS ──────────────────────────────────────────
        stats_row = QHBoxLayout()
        self.card_events = self._make_stat_card("Events", "0")
        self.card_cpu = self._make_stat_card("CPU", "0%")
        self.card_ram = self._make_stat_card("RAM", "0%")
        self.card_rate = self._make_stat_card("Events/sec", "0")
        for c in (self.card_events, self.card_cpu, self.card_ram, self.card_rate):
            stats_row.addWidget(c)
        layout.addLayout(stats_row)

        # ─── ALERT BANNER (hidden until triggered) ──────────────
        self.alert_bar = QFrame()
        self.alert_bar.setObjectName("alertBar")
        self.alert_bar.setVisible(False)
        alert_layout = QHBoxLayout(self.alert_bar)
        self.alert_label = QLabel("")
        self.alert_label.setStyleSheet("color: white; font-weight: 700;")
        alert_dismiss = QPushButton("Dismiss")
        alert_dismiss.clicked.connect(lambda: self.alert_bar.setVisible(False))
        alert_layout.addWidget(self.alert_label)
        alert_layout.addStretch()
        alert_layout.addWidget(alert_dismiss)
        layout.addWidget(self.alert_bar)

        # ─── TOOLBAR: search + filters + controls ───────────────
        tool_row = QHBoxLayout()

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search feed (entity, path, PID…)  —  Ctrl+F")
        self.search_box.textChanged.connect(self.apply_filters)
        tool_row.addWidget(self.search_box, stretch=2)

        self.subsystem_filter = QComboBox()
        self.subsystem_filter.addItems(["All subsystems", "FILESYSTEM", "PROCESS"])
        self.subsystem_filter.currentIndexChanged.connect(self.apply_filters)
        tool_row.addWidget(self.subsystem_filter)

        self.action_filter = QComboBox()
        self.action_filter.addItems(["All actions", "CREATED", "MODIFIED", "DELETED", "MOVED", "SPAWN"])
        self.action_filter.currentIndexChanged.connect(self.apply_filters)
        tool_row.addWidget(self.action_filter)

        self.pause_btn = QPushButton("⏸ Pause")
        self.pause_btn.setCheckable(True)
        self.pause_btn.clicked.connect(self.toggle_pause)
        tool_row.addWidget(self.pause_btn)

        folder_btn = QPushButton("📁 Watch folder…")
        folder_btn.clicked.connect(self.choose_folder)
        tool_row.addWidget(folder_btn)

        layout.addLayout(tool_row)

        watch_label = QLabel(f"Watching: {self.watch_path}")
        watch_label.setObjectName("muted")
        self.watch_label = watch_label
        layout.addWidget(watch_label)

        # ─── TABLE ───────────────────────────────────────────────
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["TIMESTAMP", "SUBSYSTEM", "ACTION", "TARGET / ENTITY", "RAW DETAILS"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.clicked.connect(self.display_row_details)
        self.table.setAlternatingRowColors(True)
        self.table.setFont(QFont("Segoe UI", 9))
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_row_menu)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 110)
        self.table.setColumnWidth(1, 110)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 220)
        layout.addWidget(self.table)

        # ─── INSPECTOR ───────────────────────────────────────────
        inspector_title = QLabel("EVENT INSPECTOR")
        inspector_title.setObjectName("muted")
        inspector_title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.details_box = QTextEdit()
        self.details_box.setReadOnly(True)
        self.details_box.setMaximumHeight(80)
        self.details_box.setFont(QFont("Consolas", 10))
        self.details_box.setPlaceholderText("Click any row to view its full telemetry block…")
        layout.addWidget(inspector_title)
        layout.addWidget(self.details_box)

        # ─── FOOTER ──────────────────────────────────────────────
        footer = QHBoxLayout()
        self.sound_check = QCheckBox("Alert sound")
        self.sound_check.setChecked(True)
        self.sound_check.stateChanged.connect(
            lambda s: setattr(self, "sound_alerts", bool(s)))
        footer.addWidget(self.sound_check)
        footer.addStretch()

        save_csv_btn = QPushButton("Export CSV")
        save_csv_btn.setObjectName("primary")
        save_csv_btn.clicked.connect(self.save_history_csv)

        save_json_btn = QPushButton("Export JSON")
        save_json_btn.clicked.connect(self.save_history_json)

        clear_btn = QPushButton("Clear Feed")
        clear_btn.setObjectName("danger")
        clear_btn.clicked.connect(self.clear_feed)

        footer.addWidget(save_csv_btn)
        footer.addWidget(save_json_btn)
        footer.addWidget(clear_btn)
        layout.addLayout(footer)

        self.setCentralWidget(main_widget)

        self.spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.spinner_idx = 0
        self._last_second_count = 0
        self._rate_window_start = time.time()

        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self.update_ui_loop)
        self.ui_timer.start(100)

        # shortcuts
        QAction("focus-search", self, shortcut="Ctrl+F", triggered=self.search_box.setFocus).setParent(self)
        self.addAction(self._make_shortcut("Ctrl+F", self.search_box.setFocus))
        self.addAction(self._make_shortcut("Ctrl+S", self.save_history_csv))
        self.addAction(self._make_shortcut("Space", self.pause_btn.click))

    def _make_shortcut(self, key, fn):
        act = QAction(self)
        act.setShortcut(key)
        act.triggered.connect(fn)
        return act

    def _make_stat_card(self, title, value):
        card = QFrame()
        card.setObjectName("statCard")
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 10, 14, 10)
        val_lbl = QLabel(value)
        val_lbl.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title_lbl = QLabel(title)
        title_lbl.setObjectName("muted")
        v.addWidget(val_lbl)
        v.addWidget(title_lbl)
        card._value_label = val_lbl
        return card

    # ---------------- tray ----------------
    def init_tray(self):
        self.tray = QSystemTrayIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon), self)
        menu = QMenu()
        show_action = menu.addAction("Show OmniSight")
        show_action.triggered.connect(self.showNormal)
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(QApplication.instance().quit)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip("OmniSight — running")
        self.tray.show()
        self.tray.activated.connect(
            lambda reason: self.showNormal() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)

    def closeEvent(self, event):
        self.worker.stop()
        self.tray.hide()
        event.accept()

    # ---------------- controls ----------------
    def toggle_pause(self, checked):
        self.worker.set_paused(checked)
        self.pause_btn.setText("▶ Resume" if checked else "⏸ Pause")
        self.last_action_lbl.setText("Paused" if checked else "Monitoring…")

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose folder to watch", self.watch_path)
        if folder:
            self.watch_path = folder
            self.watch_label.setText(f"Watching: {self.watch_path}")
            self.restart_worker()
            if self.pause_btn.isChecked():
                self.pause_btn.setChecked(False)
                self.toggle_pause(False)

    # ---------------- events / filtering ----------------
    def append_log_row(self, timestamp, subsystem, action, entity, details):
        self.event_count += 1
        self._last_second_count += 1
        row = (timestamp, subsystem, action, entity, details)
        self.all_rows.insert(0, row)

        emoji = ACTION_ICONS.get(action, "📝")
        self.last_action_lbl.setText(f"Last Event: {emoji} [{action}] {entity}")

        if action == "DELETED":
            self._track_deletion()

        self._render_row_if_visible(row)

    def _track_deletion(self):
        now = time.time()
        self.delete_timestamps.append(now)
        while self.delete_timestamps and now - self.delete_timestamps[0] > RANSOM_WINDOW_SECS:
            self.delete_timestamps.popleft()
        if len(self.delete_timestamps) >= RANSOM_THRESHOLD:
            self.trigger_alert(
                f"⚠ Mass deletion detected — {len(self.delete_timestamps)} files removed "
                f"in under {RANSOM_WINDOW_SECS}s. This can indicate ransomware activity."
            )
            self.delete_timestamps.clear()

    def trigger_alert(self, message):
        self.alert_label.setText(message)
        self.alert_bar.setVisible(True)
        if self.sound_alerts:
            QApplication.beep()
        self.tray.showMessage("OmniSight alert", message, QSystemTrayIcon.MessageIcon.Warning, 6000)

    def _row_matches_filters(self, row):
        timestamp, subsystem, action, entity, details = row
        query = self.search_box.text().strip().lower()
        if query and query not in entity.lower() and query not in details.lower():
            return False
        sub_choice = self.subsystem_filter.currentText()
        if sub_choice != "All subsystems" and subsystem != sub_choice:
            return False
        act_choice = self.action_filter.currentText()
        if act_choice != "All actions" and action != act_choice:
            return False
        return True

    def _render_row_if_visible(self, row):
        if not self._row_matches_filters(row):
            return
        self._insert_table_row(row, at_top=True)

    def apply_filters(self):
        self.table.setRowCount(0)
        for row in self.all_rows:
            if self._row_matches_filters(row):
                self._insert_table_row(row, at_top=False)

    def _insert_table_row(self, row, at_top):
        timestamp, subsystem, action, entity, details = row
        pos = 0
        self.table.insertRow(pos)

        item_time = QTableWidgetItem(timestamp)
        item_sub = QTableWidgetItem(subsystem)
        item_act = QTableWidgetItem(f"{ACTION_ICONS.get(action,'')} {action}")
        item_ent = QTableWidgetItem(entity)
        item_det = QTableWidgetItem(details)

        item_sub.setForeground(QColor("#4aa3ff" if subsystem == "PROCESS" else "#f4c542"))
        color = ACTION_COLORS.get(action, "#f4f2f0")
        item_act.setForeground(QColor(color))

        self.table.setItem(pos, 0, item_time)
        self.table.setItem(pos, 1, item_sub)
        self.table.setItem(pos, 2, item_act)
        self.table.setItem(pos, 3, item_ent)
        self.table.setItem(pos, 4, item_det)

    # ---------------- inspector / context menu ----------------
    def display_row_details(self):
        row = self.table.currentIndex().row()
        if row < 0:
            return
        try:
            items = [self.table.item(row, c) for c in range(5)]
            if not all(items):
                return
            timestamp, subsystem, action, entity, details = [i.text() for i in items]
            self.details_box.setPlainText(
                f"[TIMESTAMP]: {timestamp}\n"
                f"[SUBSYSTEM]: {subsystem} | [ACTION]: {action}\n"
                f"[TARGET/ENTITY]: {entity}\n"
                f"[RAW TELEMETRY DATA]: {details}"
            )
        except Exception:
            pass

    def show_row_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        menu = QMenu(self)
        copy_action = menu.addAction("Copy raw details")
        open_folder_action = menu.addAction("Open containing folder")
        chosen = menu.exec(QCursor.pos())
        details_item = self.table.item(row, 4)
        if not details_item:
            return
        if chosen == copy_action:
            QApplication.clipboard().setText(details_item.text())
        elif chosen == open_folder_action:
            path_text = details_item.text().replace("Path: ", "").split(" | ")[0]
            folder = os.path.dirname(path_text) if os.path.isabs(path_text) else self.watch_path
            if os.path.isdir(folder):
                os.startfile(folder) if os.name == "nt" else os.system(f'xdg-open "{folder}"')

    # ---------------- export ----------------
    def save_history_csv(self):
        if not self.all_rows:
            self.details_box.setPlainText("⚠️ Nothing to export: the telemetry table is empty.")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Telemetry History", os.path.expanduser("~/Desktop/telemetry_history.csv"),
            "CSV Spreadsheet (*.csv)")
        if not file_path:
            return
        try:
            with open(file_path, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["TIMESTAMP", "SUBSYSTEM", "ACTION", "TARGET_ENTITY", "RAW_DETAILS"])
                writer.writerows(self.all_rows)
            self.details_box.setPlainText(f"✅ Exported to:\n{file_path}")
        except Exception as e:
            self.details_box.setPlainText(f"❌ Failed to export:\n{str(e)}")

    def save_history_json(self):
        if not self.all_rows:
            self.details_box.setPlainText("⚠️ Nothing to export: the telemetry table is empty.")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Telemetry History", os.path.expanduser("~/Desktop/telemetry_history.json"),
            "JSON (*.json)")
        if not file_path:
            return
        try:
            payload = [
                {"timestamp": t, "subsystem": s, "action": a, "entity": e, "details": d}
                for (t, s, a, e, d) in self.all_rows
            ]
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            self.details_box.setPlainText(f"✅ Exported to:\n{file_path}")
        except Exception as e:
            self.details_box.setPlainText(f"❌ Failed to export:\n{str(e)}")

    # ---------------- loop / misc ----------------
    def update_ui_loop(self):
        self.spinner_idx = (self.spinner_idx + 1) % len(self.spinner_frames)
        self.spinner_lbl.setText(self.spinner_frames[self.spinner_idx])

        now = time.time()
        if now - self._rate_window_start >= 1:
            self.card_rate._value_label.setText(str(self._last_second_count))
            self._last_second_count = 0
            self._rate_window_start = now

            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory().percent
            self.card_events._value_label.setText(str(self.event_count))
            self.card_cpu._value_label.setText(f"{cpu}%")
            self.card_ram._value_label.setText(f"{ram}%")

    def clear_feed(self):
        self.table.setRowCount(0)
        self.all_rows.clear()
        self.event_count = 0
        self.delete_timestamps.clear()
        self.details_box.clear()
        self.alert_bar.setVisible(False)
        self.last_action_lbl.setText("Monitoring…")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    panel = TelemetryPanel()
    panel.show()
    sys.exit(app.exec())
