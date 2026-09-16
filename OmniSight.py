import sys
import os
import time
import csv
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTableWidget, QTableWidgetItem, 
                             QLabel, QHeaderView, QPushButton, QAbstractItemView,
                             QFileDialog, QTextEdit)
from PyQt6.QtCore import QTimer, QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont, QColor, QPalette
import psutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# =====================================================================
# 1. BACKGROUND TELEMETRY ENGINE
# =====================================================================

class FileWatchHandler(FileSystemEventHandler):
    def __init__(self, signal):
        super().__init__()
        self.signal = signal

    def on_any_event(self, event):
        if event.is_directory:
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

    def run(self):
        self.observer = Observer()
        handler = FileWatchHandler(self.log_signal)
        
        # Targets the full User Profile folder (Desktop, Documents, Downloads...)
        user_home = os.path.expanduser("~")
        self.observer.schedule(handler, path=user_home, recursive=True)
        self.observer.start()

        known_pids = set(psutil.pids())

        while self.isRunning():
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

class TelemetryPanel(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ilyas's Data Gathering ")
        self.resize(1100, 750) 
        self.setup_light_theme()
        self.init_ui()
        
        self.worker = TelemetryWorker()
        self.worker.log_signal.connect(self.append_log_row)
        self.worker.start()

    def setup_light_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(15, 15, 18))
        palette.setColor(QPalette.ColorRole.Base, QColor(248, 249, 250))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(240, 242, 245))
        palette.setColor(QPalette.ColorRole.Text, QColor(15, 15, 18))
        palette.setColor(QPalette.ColorRole.Button, QColor(230, 232, 235))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(15, 15, 18))
        self.setPalette(palette)

    def init_ui(self):
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(20, 20, 20, 20)

        # ─── HEADER BAR ──────────────────────────────────────────────
        header_layout = QHBoxLayout()
        
        self.title_lbl = QLabel("Live Action Data")
        self.title_lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.title_lbl.setStyleSheet("color: #0F0F12;")
        
        self.status_box = QHBoxLayout()
        self.status_box.setSpacing(8)
        
        self.spinner_lbl = QLabel("⠋")
        self.spinner_lbl.setFont(QFont("Consolas", 12))
        self.spinner_lbl.setStyleSheet("color: #0066FF;") 
        
        self.last_action_lbl = QLabel("Monitoring User Home Folder Tree...")
        self.last_action_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        self.last_action_lbl.setStyleSheet("color: #606570;")
        
        self.status_box.addWidget(self.spinner_lbl)
        self.status_box.addWidget(self.last_action_lbl)

        header_layout.addWidget(self.title_lbl)
        header_layout.addSpacing(30)
        header_layout.addLayout(self.status_box)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # ─── MAIN TABLE INTERFACE ────────────────────────────────────
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["TIMESTAMP", "SUBSYSTEM", "ACTION", "TARGET / ENTITY", "RAW DETAILS"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        
        # Connect to row clicks (Using generic click signal to bypass context menu crashes)
        self.table.clicked.connect(self.display_row_details)
        
        self.table.setAlternatingRowColors(True)
        self.table.setFont(QFont("Segoe UI", 9))

        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #F8F9FA;
                alternate-background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                gridline-color: #EDF2F7;
                color: #0F0F12;
                border-radius: 8px; 
                padding: 5px;
            }
            QHeaderView::section {
                background-color: #FFFFFF;
                color: #4A5568;
                padding: 8px;
                font-weight: bold;
                border: none;
                border-bottom: 2px solid #E2E8F0;
            }
        """)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 110)
        self.table.setColumnWidth(1, 110)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 220)
        layout.addWidget(self.table)

        # ─── INSPECTOR PANEL ─────────────────────────────────────────
        inspector_layout = QVBoxLayout()
        inspector_title = QLabel("EVENT INSPECTOR                         a detailled way to see whatever file you're holding")
        inspector_title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        inspector_title.setStyleSheet("color: #4A5568; margin-top: 5px;")
        
        self.details_box = QTextEdit()
        self.details_box.setReadOnly(True)
        self.details_box.setMaximumHeight(80)
        self.details_box.setFont(QFont("Consolas", 10))
        self.details_box.setPlaceholderText("Click on any row inside the table feed to view its complete telemetry details block...")
        self.details_box.setStyleSheet("""
            QTextEdit {
                background-color: #F1F5F9;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 8px;
                color: #1E293B;
            }
        """)
        inspector_layout.addWidget(inspector_title)
        inspector_layout.addWidget(self.details_box)
        layout.addLayout(inspector_layout)

        # ─── FOOTER BAR (STATS & BUTTONS) ────────────────────────────
        footer_layout = QHBoxLayout()
        
        self.stats_lbl = QLabel("Events Logged: 0 | CPU: 0% | RAM: 0%")
        self.stats_lbl.setFont(QFont("Segoe UI", 9))
        self.stats_lbl.setStyleSheet("color: #718096;")
        
        save_btn = QPushButton("Save History")
        save_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        save_btn.setFixedSize(110, 32)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #DCFCE7; 
                color: #16A34A; 
                border: 1px solid #BBF7D0; 
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #BBF7D0;
                color: #15803D;
            }
        """)
        save_btn.clicked.connect(self.save_history)

        clear_btn = QPushButton("Clear Feed")
        clear_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        clear_btn.setFixedSize(110, 32)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #FEE2E2; 
                color: #EF4444; 
                border: 1px solid #FCA5A5; 
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #FCA5A5;
                color: #B91C1C;
            }
        """)
        clear_btn.clicked.connect(self.clear_feed)
        
        footer_layout.addWidget(self.stats_lbl)
        footer_layout.addStretch()
        footer_layout.addWidget(save_btn)
        footer_layout.addSpacing(5)
        footer_layout.addWidget(clear_btn)
        layout.addLayout(footer_layout)

        self.setCentralWidget(main_widget)

        self.event_count = 0
        self.spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.spinner_idx = 0
        
        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self.update_ui_loop)
        self.ui_timer.start(100) 
# =====================================================================
# 2. CLEAN MODERN LIGHT UI (PART B: LOGIC & FIXED SELECTION ENGINE)
# =====================================================================

    def append_log_row(self, timestamp, subsystem, action, entity, details):
        self.event_count += 1
        row_pos = 0 
        self.table.insertRow(row_pos)
        
        item_time = QTableWidgetItem(timestamp)
        item_sub = QTableWidgetItem(subsystem)
        item_act = QTableWidgetItem(action)
        item_ent = QTableWidgetItem(entity)
        item_det = QTableWidgetItem(details)

        if subsystem == "PROCESS":
            item_sub.setForeground(QColor("#0066FF")) 
        else:
            item_sub.setForeground(QColor("#DD6B20")) 

        emoji = "📝" 
        if "DELETED" in action:
            item_act.setForeground(QColor("#E53E3E"))
            emoji = "🗑️"
        elif "CREATED" in action:
            emoji = "🆕"
        elif "MOVED" in action or "MODIFIED" in action:
            emoji = "📝"
        elif "SPAWN" in action:
            emoji = "🚀"

        self.last_action_lbl.setText(f"Last Event: {emoji} [{action}] {entity}")
        self.last_action_lbl.setStyleSheet("color: #0F0F12; font-weight: bold;")

        self.table.setItem(row_pos, 0, item_time)
        self.table.setItem(row_pos, 1, item_sub)
        self.table.setItem(row_pos, 2, item_act)
        self.table.setItem(row_pos, 3, item_ent)
        self.table.setItem(row_pos, 4, item_det)

    def display_row_details(self):
        """FIXED: Uses native index rows. Totally immuned against NoneType and List attribute crashes."""
        row = self.table.currentIndex().row()
        if row < 0:
            return
            
        try:
            item_0 = self.table.item(row, 0)
            item_1 = self.table.item(row, 1)
            item_2 = self.table.item(row, 2)
            item_3 = self.table.item(row, 3)
            item_4 = self.table.item(row, 4)
            
            if not all([item_0, item_1, item_2, item_3, item_4]):
                return

            timestamp = item_0.text()
            subsystem = item_1.text()
            action = item_2.text()
            entity = item_3.text()
            details = item_4.text()
            
            formatted_text = (
                f"[TIMESTAMP]: {timestamp}\n"
                f"[SUBSYSTEM]: {subsystem} | [ACTION]: {action}\n"
                f"[TARGET/ENTITY]: {entity}\n"
                f"[RAW TELEMETRY DATA]: {details}"
            )
            self.details_box.setPlainText(formatted_text)
        except Exception:
            pass 

    def save_history(self):
        if self.table.rowCount() == 0:
            self.details_box.setPlainText("⚠️ Cannot export log feed: The telemetry table is currently empty.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Export Telemetry History Log", 
            os.path.expanduser("~/Desktop/telemetry_history.csv"), 
            "CSV Spreadsheet (*.csv)"
        )
        
        if file_path:
            try:
                with open(file_path, mode='w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["TIMESTAMP", "SUBSYSTEM", "ACTION", "TARGET_ENTITY", "RAW_DETAILS"])
                    
                    for row in reversed(range(self.table.rowCount())):
                        writer.writerow([
                            self.table.item(row, 0).text(),
                            self.table.item(row, 1).text(),
                            self.table.item(row, 2).text(),
                            self.table.item(row, 3).text(),
                            self.table.item(row, 4).text()
                        ])
                        
                self.details_box.setPlainText(f"✅ History logged successfully exported to:\n{file_path}")
            except Exception as e:
                self.details_box.setPlainText(f"❌ Failed to write file down due to system error:\n{str(e)}")

    def update_ui_loop(self):
        self.spinner_idx = (self.spinner_idx + 1) % len(self.spinner_frames)
        self.spinner_lbl.setText(self.spinner_frames[self.spinner_idx])
        
        if time.time() % 1 < 0.15:
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory().percent
            self.stats_lbl.setText(f"Events Logged: {self.event_count} | CPU: {cpu}% | RAM: {ram}%")

    def clear_feed(self):
        self.table.setRowCount(0)
        self.event_count = 0
        self.details_box.clear()
        self.last_action_lbl.setText("Monitoring User Home Folder Tree...")
        self.last_action_lbl.setStyleSheet("color: #606570; font-weight: normal;")

    def closeEvent(self, event):
        self.worker.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    panel = TelemetryPanel()
    panel.show()
    sys.exit(app.exec())
