"""TrackerGUI extraction.

Depends on window_detection.find_target_window, mouse_tracker.MouseTracker and screenshot_gui.ScreenshotGUI.
Implementation copied with minimal changes.
"""

from __future__ import annotations
from typing import Dict
import logging
import os
import subprocess
import sys
from PIL import ImageGrab
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QHeaderView,
    QTableWidgetItem,
    QApplication,
)
import pyperclip
import pyautogui
from shared_utilities.mouse_tracker import MouseTracker
from shared_utilities.window_detection import find_target_window
from screenshot_gui import ScreenshotGUI


class TrackerGUI(QWidget):
    def __init__(self, target_process="WidgetInc.exe"):
        super().__init__()
        self.target_process = target_process
        self.logger = logging.getLogger(self.__class__.__name__)
        self.target_found = False
        self.target_hwnd = None
        self.coordinates = {}
        self.window_xy = {}
        self.frame_xy = {}
        self.frozen = False
        self.mouse_tracker = MouseTracker()
        self.mouse_tracker.set_coordinate_callbacks(self._get_window_coords, self._get_frame_coords)
        self.mouse_tracker.position_changed.connect(self._on_mouse_position_changed)
        self._setup_window()
        self._setup_ui()
        self._start_monitoring()
        self.mouse_tracker.start_tracking(100)
        self.logger.info("Tracker widget initialized")

    def _setup_window(self):
        self.setWindowTitle("Widget Automation Tracker")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setFixedSize(325, 400)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet("""
            QWidget { background-color: #2d2d2d; color: #ffffff; font-family: 'Segoe UI', Arial, sans-serif; }
            QLabel { background-color: transparent; }
        """)
        screen = QApplication.primaryScreen()
        if screen is not None:
            rect = screen.availableGeometry() if hasattr(screen, "availableGeometry") else screen.geometry()
            self.move((rect.width() - self.width()) // 2, (rect.height() - self.height()) // 2)
        else:
            self.move(50, 50)

    def _setup_ui(self):  # Highly condensed; refer to original for full styling (kept minimal here)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        self.title_label = QLabel("Widget Tracker")
        self.title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("""QLabel { color:#fff; padding:8px; background:#3d3d3d; border-radius:4px; }""")
        hotkey_label = QLabel("Ctrl+F to freeze coordinates")
        hotkey_label.setFont(QFont("Arial", 8))
        hotkey_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hotkey_label.setStyleSheet("QLabel { color:#888; font-style:italic; }")
        status_layout = QHBoxLayout()
        self.status_label = QLabel("SEARCHING...")
        self.status_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.status_label.setStyleSheet("QLabel { color:#ccc; }")
        self.status_circle = QLabel()
        self.status_circle.setFixedSize(20, 20)
        self.status_circle.setStyleSheet("QLabel { background:#FF8C00; border-radius:10px; border:2px solid #FFA500; }")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.status_circle)
        self.coords_table = QTableWidget(2, 2)
        self.coords_table.setHorizontalHeaderLabels(["Top-Left", "Dimensions"])
        self.coords_table.setVerticalHeaderLabels(["Window", "Frame"])
        self.coords_table.setFixedHeight(90)
        if h := self.coords_table.horizontalHeader():
            h.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        if v := self.coords_table.verticalHeader():
            v.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.coords_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.coords_table.setStyleSheet(
            """QTableWidget {background:#1e1e1e; color:#fff; border:1px solid #555; font-family:'Consolas','Courier New',monospace; font-size:9pt;} QHeaderView::section {background:#3d3d3d; font-weight:bold;}"""
        )
        self._init_coords_table()
        button_layout = QHBoxLayout()
        self.screenshot_button = QPushButton("SCREENSHOT")
        self.screenshot_button.clicked.connect(self._take_screenshot)
        self.restart_button = QPushButton("RESTART")
        self.restart_button.clicked.connect(self._restart_application)
        self.close_button = QPushButton("CLOSE")
        self.close_button.clicked.connect(self.close)
        for b, color in (
            (self.screenshot_button, "#388e3c"),
            (self.restart_button, "#1976d2"),
            (self.close_button, "#d32f2f"),
        ):
            b.setStyleSheet(
                f"QPushButton {{background:{color}; color:#fff; border:none; padding:8px 16px; border-radius:4px; font-weight:bold;}}"
            )
        button_layout.addWidget(self.screenshot_button)
        button_layout.addStretch()
        button_layout.addWidget(self.restart_button)
        button_layout.addWidget(self.close_button)
        self.mouse_table = QTableWidget(4, 2)
        self.mouse_table.setHorizontalHeaderLabels(["Actuals", "Percents"])
        self.mouse_table.setVerticalHeaderLabels(["Screen", "Window", "Frame", "Color"])
        self.mouse_table.setFixedHeight(140)
        if h := self.mouse_table.horizontalHeader():
            h.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        if v := self.mouse_table.verticalHeader():
            v.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.mouse_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.mouse_table.cellClicked.connect(self.on_cell_clicked)
        self.mouse_table.setStyleSheet(
            """QTableWidget {background:#1e1e1e; color:#00ff88; border:1px solid #555; font-family:'Fira Code','Consolas','Courier New',monospace; font-size:9pt;} QHeaderView::section {background:#3d3d3d; font-weight:bold;} QTableWidget::item:selected {background:#1e1e1e; color:#ff0000;}"""
        )
        self._init_mouse_table()
        layout.addWidget(self.title_label)
        layout.addWidget(hotkey_label)
        layout.addLayout(status_layout)
        layout.addWidget(self.coords_table)
        layout.addWidget(self.mouse_table)
        layout.addLayout(button_layout)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        close_action = QAction("Close", self)
        close_action.triggered.connect(self.close)
        self.addAction(close_action)

    def _init_coords_table(self):
        self.coords_table.setItem(0, 0, QTableWidgetItem("N/A"))
        self.coords_table.setItem(0, 1, QTableWidgetItem("N/A"))
        self.coords_table.setItem(1, 0, QTableWidgetItem("N/A"))
        self.coords_table.setItem(1, 1, QTableWidgetItem("N/A"))

    def _init_mouse_table(self):
        self.mouse_table.setItem(0, 0, QTableWidgetItem("0, 0"))
        self.mouse_table.setItem(0, 1, QTableWidgetItem("N/A"))
        self.mouse_table.setItem(1, 0, QTableWidgetItem("Outside"))
        self.mouse_table.setItem(1, 1, QTableWidgetItem("N/A"))
        self.mouse_table.setItem(2, 0, QTableWidgetItem("Outside"))
        self.mouse_table.setItem(2, 1, QTableWidgetItem("N/A"))
        self.mouse_table.setItem(3, 0, QTableWidgetItem("#000000"))
        self.mouse_table.setItem(3, 1, QTableWidgetItem("0, 0, 0"))

    def on_cell_clicked(self, row: int, column: int):
        item = self.mouse_table.item(row, column)
        if not item:
            return
        text = item.text()
        if text in ("N/A", "Outside"):
            return
        copied_text = ""
        if column == 1 and "%" in text:
            percentages = []
            for part in text.replace("%", "").split(", "):
                try:
                    percentages.append(f"{float(part) / 100:.6f}")
                except ValueError:
                    continue
            if percentages:
                copied_text = ", ".join(percentages)
                pyperclip.copy(copied_text)
        else:
            copied_text = text
            pyperclip.copy(text)
        if copied_text:
            self.logger.info(f"Copied to clipboard: {copied_text}")
            self._show_copy_feedback(copied_text)

    def _take_screenshot(self):
        if not self.frame_xy:
            return
        try:
            fx = self.frame_xy.get("x", 0)
            fy = self.frame_xy.get("y", 0)
            fw = self.frame_xy.get("width", 0)
            fh = self.frame_xy.get("height", 0)
            if fw <= 0 or fh <= 0:
                return
            bbox = (fx, fy, fx + fw, fy + fh)
            screenshot = ImageGrab.grab(bbox=bbox, all_screens=True)
            viewer = ScreenshotGUI(self.frame_xy.copy(), screenshot, parent=self)
            viewer.show()
            if not hasattr(self, "_screenshot_viewers"):
                self._screenshot_viewers = []
            self._screenshot_viewers.append(viewer)

            self.logger.info(f"Screenshot taken: {fw}x{fh} at ({fx}, {fy})")
        except Exception as e:
            self.logger.error(f"Failed to take screenshot: {e}")

    def _remove_viewer(self, viewer):
        """Remove a screenshot viewer from the tracked list."""
        if hasattr(self, "_screenshot_viewers") and viewer in self._screenshot_viewers:
            self._screenshot_viewers.remove(viewer)

    def _start_monitoring(self):
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._check_target)
        self.monitor_timer.start(2000)
        self._check_target()

    def _check_target(self):
        target_info = find_target_window(self.target_process)
        if target_info:
            pid = target_info["pid"]
            window_info = target_info["window_info"]
            frame_area = target_info["frame_area"]
            found_info = {
                "pid": pid,
                "hwnd": window_info["hwnd"],
                "title": window_info["title"],
                "rect": window_info["window_rect"],
                "client_rect": (0, 0, window_info["client_width"], window_info["client_height"]),
                "window_info": window_info,
                "frame_area": frame_area,
                "refinement_applied": target_info.get("refinement_applied", False),
            }
            self._update_status(True, found_info)
        else:
            self._update_status(False, {})

    def _update_status(self, found: bool, target_info: dict):
        if found:
            pid = target_info.get("pid", "unknown")
            self.status_label.setText(f"{self.target_process} (PID: {pid})")
            self.status_circle.setStyleSheet(
                "QLabel { background:#4CAF50; border-radius:10px; border:2px solid #66BB6A; }"
            )
            if "rect" in target_info:
                rect = target_info["rect"]
                ww = rect[2] - rect[0]
                wh = rect[3] - rect[1]
                self.coords_table.setItem(0, 0, QTableWidgetItem(f"{rect[0]}, {rect[1]}"))
                self.coords_table.setItem(0, 1, QTableWidgetItem(f"{ww}x{wh}"))
                if target_info.get("frame_area"):
                    frame = target_info["frame_area"]
                    self.coords_table.setItem(1, 0, QTableWidgetItem(f"{frame['x']}, {frame['y']}"))
                    self.coords_table.setItem(1, 1, QTableWidgetItem(f"{frame['width']}x{frame['height']}"))
                    self.window_xy = target_info["window_info"]
                    self.frame_xy = frame
                else:
                    self.coords_table.setItem(1, 0, QTableWidgetItem("N/A"))
                    self.coords_table.setItem(1, 1, QTableWidgetItem("N/A"))
        elif self.target_found:
            self.status_label.setText("SEARCHING...")
            self.status_circle.setStyleSheet(
                "QLabel { background:#FFA500; border-radius:10px; border:2px solid #FF8C00; }"
            )
            for row in range(2):
                self.coords_table.setItem(row, 0, QTableWidgetItem("N/A"))
                self.coords_table.setItem(row, 1, QTableWidgetItem("N/A"))
            self.window_xy = {}
            self.frame_xy = {}
        self.target_found = found

    def _get_window_coords(self) -> Dict:
        return self.window_xy

    def _get_frame_coords(self) -> Dict:
        return self.frame_xy

    def _on_mouse_position_changed(self, position_info: Dict):
        if self.frozen:
            return
        try:
            sx = position_info.get("screen_x", 0)
            sy = position_info.get("screen_y", 0)
            try:
                color = pyautogui.pixel(sx, sy)
                hex_color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
                rgb_color = f"{color[0]}, {color[1]}, {color[2]}"
            except Exception:
                hex_color = "#000000"
                rgb_color = "0, 0, 0"
            self.mouse_table.setItem(0, 0, QTableWidgetItem(f"{sx}, {sy}"))
            self.mouse_table.setItem(0, 1, QTableWidgetItem("N/A"))
            if position_info.get("inside_window", False):
                wxp = position_info.get("window_x_percent", 0)
                wyp = position_info.get("window_y_percent", 0)
                self.mouse_table.setItem(1, 0, QTableWidgetItem(f"{sx}, {sy}"))
                self.mouse_table.setItem(1, 1, QTableWidgetItem(f"{wxp:.2f}%, {wyp:.2f}%"))
            else:
                self.mouse_table.setItem(1, 0, QTableWidgetItem("Outside"))
                self.mouse_table.setItem(1, 1, QTableWidgetItem("N/A"))
            if position_info.get("inside_window", False):
                if position_info.get("inside_frame", False):
                    fx = position_info.get("frame_x", 0)
                    fy = position_info.get("frame_y", 0)
                    xp = position_info.get("x_percent", 0)
                    yp = position_info.get("y_percent", 0)
                    self.mouse_table.setItem(2, 0, QTableWidgetItem(f"{fx}, {fy}"))
                    self.mouse_table.setItem(2, 1, QTableWidgetItem(f"{xp:.2f}%, {yp:.2f}%"))
                else:
                    if self.frame_xy:
                        fxr = sx - self.frame_xy.get("x", 0)
                        fyr = sy - self.frame_xy.get("y", 0)
                        fw = self.frame_xy.get("width", 1)
                        fh = self.frame_xy.get("height", 1)
                        fx = max(0, min(fxr, fw))
                        fy = max(0, min(fyr, fh))
                        xp = max(0.0, min(100.0, 100 * fxr / max(1, fw)))
                        yp = max(0.0, min(100.0, 100 * fyr / max(1, fh)))
                        self.mouse_table.setItem(2, 0, QTableWidgetItem(f"{fx}, {fy}"))
                        self.mouse_table.setItem(2, 1, QTableWidgetItem(f"{xp:.2f}%, {yp:.2f}%"))
                    else:
                        self.mouse_table.setItem(2, 0, QTableWidgetItem("N/A"))
                        self.mouse_table.setItem(2, 1, QTableWidgetItem("N/A"))
            else:
                self.mouse_table.setItem(2, 0, QTableWidgetItem("Outside"))
                self.mouse_table.setItem(2, 1, QTableWidgetItem("N/A"))
            self.mouse_table.setItem(3, 0, QTableWidgetItem(hex_color))
            self.mouse_table.setItem(3, 1, QTableWidgetItem(rgb_color))
        except Exception as e:
            self.logger.error(f"Error updating mouse display: {e}")
            for row in range(4):
                self.mouse_table.setItem(row, 0, QTableWidgetItem("Error"))
                self.mouse_table.setItem(row, 1, QTableWidgetItem("Error"))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.frozen = not self.frozen
            freeze_status = "FROZEN" if self.frozen else "TRACKING"
            orig_title = self.windowTitle()
            self.setWindowTitle(f"Widget Tracker - {freeze_status}")
            QTimer.singleShot(1500, lambda: self.setWindowTitle(orig_title))
        else:
            super().keyPressEvent(event)

    def _show_copy_feedback(self, copied_text: str):
        orig_title = self.windowTitle()
        orig_text = self.title_label.text()
        self.setWindowTitle(f"Widget Tracker - Copied: {copied_text}")
        self.title_label.setText(f"Copied: {copied_text}")
        self._show_title_copied_feedback()
        QTimer.singleShot(2000, lambda: self.setWindowTitle(orig_title))
        QTimer.singleShot(2000, lambda: self.title_label.setText(orig_text))

    def _show_title_copied_feedback(self):
        self.title_label.setStyleSheet("QLabel { color:#fff; padding:8px; background:#2ecc40; border-radius:4px; }")
        QTimer.singleShot(2000, self._reset_title_label_style)

    def _reset_title_label_style(self):
        self.title_label.setStyleSheet("QLabel { color:#fff; padding:8px; background:#3d3d3d; border-radius:4px; }")

    def _restart_application(self):
        try:
            self.logger.info("Restarting tracker application...")
            # Use the current Python interpreter (typically the venv from start.bat)
            py = sys.executable
            args = None

            if getattr(sys, "frozen", False):
                # PyInstaller/py2exe-style executable
                args = [py] + sys.argv[1:]
            else:
                # Try to relaunch the same entrypoint that started this process
                main_mod = sys.modules.get("__main__")
                spec = getattr(main_mod, "__spec__", None) if main_mod else None
                main_file = getattr(main_mod, "__file__", None) if main_mod else None

                if spec and getattr(spec, "name", None):
                    # Invoked as a module: python -m package.module
                    args = [py, "-m", spec.name] + sys.argv[1:]
                elif main_file:
                    # Invoked as a script file: python path/to/main.py
                    args = [py, main_file] + sys.argv[1:]
                else:
                    # Fallback: try src/main.py next to this package
                    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
                    main_candidate = os.path.join(base, "main.py")
                    if os.path.exists(main_candidate):
                        args = [py, main_candidate] + sys.argv[1:]
                    else:
                        # Last resort: rerun current argv as-is
                        args = [py] + sys.argv

            # Spawn new instance, then close this one
            subprocess.Popen(args, cwd=os.getcwd())
            QApplication.quit()
        except Exception as e:
            self.logger.error(f"Failed to restart application: {e}")

    def closeEvent(self, event):
        """Close all screenshot viewers when TrackerGUI closes."""
        # Close all open screenshot viewers
        if hasattr(self, "_screenshot_viewers"):
            for viewer in self._screenshot_viewers[:]:  # Copy list to avoid modification during iteration
                if viewer and not viewer.isHidden():
                    viewer.close()
            self._screenshot_viewers.clear()

        self.logger.info("TrackerGUI closing - all screenshot viewers closed")
        super().closeEvent(event)
