#!/usr/bin/env python3
"""
Main tracker widget for Widget Window Spy.
Provides coordinate tracking and window monitoring interface.
"""

import logging
import os
import subprocess
import sys
from typing import Dict

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.constants import (
    APP_TITLE,
    TARGET_PROCESS_DEFAULT,
    WINDOW_STAYS_ON_TOP,
    FONT_FAMILY,
    FONT_SIZE_TITLE,
    FONT_SIZE_COORDINATES,
    COLOR_BACKGROUND_PRIMARY,
    COLOR_BACKGROUND_TERTIARY,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_ACCENT,
    COLOR_ACCENT_GREEN,
    COLOR_ACCENT_BLUE,
    COLOR_ACCENT_YELLOW,
    COLOR_ACCENT_RED,
    COLOR_BORDER,
    TIMER_MONITOR_INTERVAL,
    TIMER_FEEDBACK_DURATION,
    TABLE_HEIGHT_COORDS,
    TABLE_HEIGHT_MOUSE,
    WIDGET_MIN_WIDTH,
    WIDGET_MIN_HEIGHT,
    WIDGET_MAX_WIDTH,
    WIDGET_MAX_HEIGHT,
    COORD_FORMAT_NA,
    COORD_FORMAT_OUTSIDE,
    COORD_FORMAT_ERROR,
)
from core.mouse_tracker import MouseTracker
from utils.window_detection import find_target_window
from ui.screenshot_viewer import ScreenshotViewer


class TrackerWidget(QWidget):
    """
    Main tracker widget providing coordinate monitoring and window tracking.
    Features freeze functionality, clipboard integration, and screenshot capture.
    """

    def __init__(self, target_process: str = TARGET_PROCESS_DEFAULT):
        super().__init__()
        self.target_process = target_process
        self.logger = logging.getLogger(self.__class__.__name__)

        # State management
        self.target_found = False
        self.target_hwnd = None
        self.coordinates = {}
        self.window_xy = {}
        self.frame_xy = {}
        self.frozen = False

        # Mouse tracking
        self.mouse_tracker = MouseTracker()
        self.mouse_tracker.set_coordinate_callbacks(self._get_window_coords, self._get_frame_coords)
        self.mouse_tracker.position_changed.connect(self._on_mouse_position_changed)

        # Screenshot viewer references
        self._screenshot_viewers = []

        # Initialize UI
        self._setup_window()
        self._setup_ui()
        self._start_monitoring()
        self.mouse_tracker.start_tracking()

        self.logger.info(f"Tracker widget initialized for {target_process}")

    def _setup_window(self) -> None:
        """Configure window properties and styling."""
        self.setWindowTitle(APP_TITLE)
        if WINDOW_STAYS_ON_TOP:
            self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMinimumSize(WIDGET_MIN_WIDTH, WIDGET_MIN_HEIGHT)
        self.setMaximumSize(WIDGET_MAX_WIDTH, WIDGET_MAX_HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Apply dark theme
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {COLOR_BACKGROUND_PRIMARY};
                color: {COLOR_TEXT_PRIMARY};
                font-family: {FONT_FAMILY};
            }}
            QLabel {{
                background-color: transparent;
            }}
        """)

        # Center window on screen
        self._center_window()

    def _center_window(self) -> None:
        """Center window on primary screen."""
        screen = QApplication.primaryScreen()
        if screen:
            rect = screen.availableGeometry()
            center_x = (rect.width() - self.width()) // 2
            center_y = (rect.height() - self.height()) // 2
            self.move(center_x, center_y)
        else:
            self.move(50, 50)

    def _setup_ui(self) -> None:
        """Create and configure user interface elements."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Title section
        self._create_title_section(layout)

        # Status section
        self._create_status_section(layout)

        # Coordinates table
        self._create_coordinates_table(layout)

        # Mouse tracking table
        self._create_mouse_table(layout)

        # Control buttons
        self._create_control_buttons(layout)

        # Context menu
        self._setup_context_menu()

    def _create_title_section(self, layout: QVBoxLayout) -> None:
        """Create title and hotkey hint sections."""
        # Main title
        self.title_label = QLabel("Widget Tracker")
        self.title_label.setFont(QFont("Arial", FONT_SIZE_TITLE, QFont.Weight.Bold))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet(f"""
            QLabel {{
                color: {COLOR_TEXT_PRIMARY};
                padding: 8px;
                background-color: {COLOR_BACKGROUND_TERTIARY};
                border-radius: 4px;
                margin-bottom: 4px;
            }}
        """)

        # Hotkey hint
        hotkey_label = QLabel("Ctrl+F to freeze coordinates")
        hotkey_label.setFont(QFont("Arial", 8))
        hotkey_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hotkey_label.setStyleSheet(f"""
            QLabel {{
                color: {COLOR_TEXT_SECONDARY};
                padding: 2px;
                background-color: transparent;
                font-style: italic;
            }}
        """)

        layout.addWidget(self.title_label)
        layout.addWidget(hotkey_label)

    def _create_status_section(self, layout: QVBoxLayout) -> None:
        """Create status indicator section."""
        status_layout = QHBoxLayout()

        self.status_label = QLabel("SEARCHING...")
        self.status_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {COLOR_TEXT_SECONDARY};
                padding: 4px;
                background-color: transparent;
            }}
        """)

        # Status indicator circle
        self.status_circle = QLabel()
        self.status_circle.setFixedSize(20, 20)
        self.status_circle.setStyleSheet(f"""
            QLabel {{
                background-color: {COLOR_ACCENT_YELLOW};
                border-radius: 10px;
                border: 2px solid {COLOR_ACCENT_YELLOW};
            }}
        """)

        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.status_circle)

        layout.addLayout(status_layout)

    def _create_coordinates_table(self, layout: QVBoxLayout) -> None:
        """Create window and frame coordinates table."""
        self.coords_table = QTableWidget(2, 2)
        self.coords_table.setHorizontalHeaderLabels(["Top-Left", "Dimensions"])
        self.coords_table.setVerticalHeaderLabels(["Window", "Frame"])

        self.coords_table.setFixedHeight(TABLE_HEIGHT_COORDS)
        self.coords_table.setAlternatingRowColors(True)

        # Configure headers
        h_header = self.coords_table.horizontalHeader()
        if h_header:
            h_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        v_header = self.coords_table.verticalHeader()
        if v_header:
            v_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.coords_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

        # Apply styling
        self.coords_table.setStyleSheet(self._get_table_stylesheet())

        # Initialize with default values
        self._init_coords_table()

        layout.addWidget(self.coords_table)

    def _create_mouse_table(self, layout: QVBoxLayout) -> None:
        """Create mouse tracking table."""
        self.mouse_table = QTableWidget(4, 2)
        self.mouse_table.setHorizontalHeaderLabels(["Actuals", "Percents"])
        self.mouse_table.setVerticalHeaderLabels(["Screen", "Window", "Frame", "Color"])

        self.mouse_table.setFixedHeight(TABLE_HEIGHT_MOUSE)
        self.mouse_table.setAlternatingRowColors(True)

        # Configure headers
        h_header = self.mouse_table.horizontalHeader()
        if h_header:
            h_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        v_header = self.mouse_table.verticalHeader()
        if v_header:
            v_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.mouse_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.mouse_table.cellClicked.connect(self.on_cell_clicked)

        # Apply special styling for mouse table
        self.mouse_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLOR_BACKGROUND_PRIMARY};
                color: {COLOR_TEXT_ACCENT};
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
                gridline-color: {COLOR_BORDER};
                font-family: {FONT_FAMILY};
                font-size: {FONT_SIZE_COORDINATES}pt;
            }}
            QTableWidget::item {{
                padding: 4px;
                border: none;
            }}
            QTableWidget::item:selected {{
                background-color: {COLOR_BACKGROUND_PRIMARY};
                color: {COLOR_ACCENT_RED};
            }}
            QHeaderView::section {{
                background-color: {COLOR_BACKGROUND_TERTIARY};
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid {COLOR_BORDER};
                padding: 4px;
                font-weight: bold;
            }}
        """)

        # Initialize with default values
        self._init_mouse_table()

        layout.addWidget(self.mouse_table)

    def _create_control_buttons(self, layout: QVBoxLayout) -> None:
        """Create control button section."""
        button_layout = QHBoxLayout()

        # Screenshot button
        self.screenshot_button = QPushButton("SCREENSHOT")
        self.screenshot_button.clicked.connect(self._take_screenshot)
        self.screenshot_button.setStyleSheet(self._get_button_stylesheet(COLOR_ACCENT_GREEN))

        # Restart button
        self.restart_button = QPushButton("RESTART")
        self.restart_button.clicked.connect(self._restart_application)
        self.restart_button.setStyleSheet(self._get_button_stylesheet(COLOR_ACCENT_BLUE))

        # Close button
        self.close_button = QPushButton("CLOSE")
        self.close_button.clicked.connect(self.close)
        self.close_button.setStyleSheet(self._get_button_stylesheet(COLOR_ACCENT_RED))

        button_layout.addWidget(self.screenshot_button)
        button_layout.addStretch()
        button_layout.addWidget(self.restart_button)
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

    def _setup_context_menu(self) -> None:
        """Setup context menu."""
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)

        close_action = QAction("Close", self)
        close_action.triggered.connect(self.close)
        self.addAction(close_action)

    def _get_table_stylesheet(self) -> str:
        """Get standard table stylesheet."""
        return f"""
            QTableWidget {{
                background-color: {COLOR_BACKGROUND_PRIMARY};
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
                gridline-color: {COLOR_BORDER};
                font-family: {FONT_FAMILY};
                font-size: {FONT_SIZE_COORDINATES}pt;
            }}
            QTableWidget::item {{
                padding: 4px;
                border: none;
            }}
            QHeaderView::section {{
                background-color: {COLOR_BACKGROUND_TERTIARY};
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid {COLOR_BORDER};
                padding: 4px;
                font-weight: bold;
            }}
        """

    def _get_button_stylesheet(self, base_color: str) -> str:
        """Get button stylesheet with specified base color."""
        # Calculate hover and pressed colors (simplified)
        return f"""
            QPushButton {{
                background-color: {base_color};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {base_color};
                opacity: 0.8;
            }}
            QPushButton:pressed {{
                background-color: {base_color};
                opacity: 0.6;
            }}
        """

    def _init_coords_table(self) -> None:
        """Initialize coordinates table with default values."""
        for row in range(2):
            for col in range(2):
                self.coords_table.setItem(row, col, QTableWidgetItem(COORD_FORMAT_NA))

    def _init_mouse_table(self) -> None:
        """Initialize mouse table with default values."""
        self.mouse_table.setItem(0, 0, QTableWidgetItem("0, 0"))
        self.mouse_table.setItem(0, 1, QTableWidgetItem(COORD_FORMAT_NA))
        self.mouse_table.setItem(1, 0, QTableWidgetItem(COORD_FORMAT_OUTSIDE))
        self.mouse_table.setItem(1, 1, QTableWidgetItem(COORD_FORMAT_NA))
        self.mouse_table.setItem(2, 0, QTableWidgetItem(COORD_FORMAT_OUTSIDE))
        self.mouse_table.setItem(2, 1, QTableWidgetItem(COORD_FORMAT_NA))
        self.mouse_table.setItem(3, 0, QTableWidgetItem("#000000"))
        self.mouse_table.setItem(3, 1, QTableWidgetItem("0, 0, 0"))

    def _start_monitoring(self) -> None:
        """Start monitoring for target process."""
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._check_target)
        self.monitor_timer.start(TIMER_MONITOR_INTERVAL)
        self._check_target()  # Initial check

    def _check_target(self) -> None:
        """Check for target process and update status."""
        target_info = find_target_window(self.target_process)

        if target_info:
            # Create compatible info structure
            found_info = {
                "pid": target_info["pid"],
                "hwnd": target_info["window_info"]["hwnd"],
                "title": target_info["window_info"]["title"],
                "rect": target_info["window_info"]["window_rect"],
                "client_rect": (
                    0,
                    0,
                    target_info["window_info"]["client_width"],
                    target_info["window_info"]["client_height"],
                ),
                "window_info": target_info["window_info"],
                "frame_area": target_info["frame_area"],
                "refinement_applied": target_info.get("refinement_applied", False),
            }
            self._update_status(True, found_info)
        else:
            self._update_status(False, {})

    def _update_status(self, found: bool, target_info: Dict) -> None:
        """Update status display and coordinate information."""
        if found:
            # Update status indicators
            pid = target_info.get("pid", "unknown")
            self.status_label.setText(f"{self.target_process} (PID: {pid})")
            self.status_circle.setStyleSheet(f"""
                QLabel {{
                    background-color: {COLOR_ACCENT_GREEN};
                    border-radius: 10px;
                    border: 2px solid {COLOR_ACCENT_GREEN};
                }}
            """)

            # Update coordinate tables
            if "rect" in target_info:
                rect = target_info["rect"]
                window_width = rect[2] - rect[0]
                window_height = rect[3] - rect[1]
                self.coords_table.setItem(0, 0, QTableWidgetItem(f"{rect[0]}, {rect[1]}"))
                self.coords_table.setItem(0, 1, QTableWidgetItem(f"{window_width}x{window_height}"))

            if "frame_area" in target_info and target_info["frame_area"]:
                frame = target_info["frame_area"]
                self.coords_table.setItem(1, 0, QTableWidgetItem(f"{frame['x']}, {frame['y']}"))
                self.coords_table.setItem(1, 1, QTableWidgetItem(f"{frame['width']}x{frame['height']}"))
                self.window_xy = target_info["window_info"]
                self.frame_xy = frame
            else:
                self.coords_table.setItem(1, 0, QTableWidgetItem(COORD_FORMAT_NA))
                self.coords_table.setItem(1, 1, QTableWidgetItem(COORD_FORMAT_NA))

        elif self.target_found:
            # Only update when transitioning from found to not found
            self.status_label.setText("SEARCHING...")
            self.status_circle.setStyleSheet(f"""
                QLabel {{
                    background-color: {COLOR_ACCENT_YELLOW};
                    border-radius: 10px;
                    border: 2px solid {COLOR_ACCENT_YELLOW};
                }}
            """)

            # Reset coordinate tables
            for row in range(2):
                for col in range(2):
                    self.coords_table.setItem(row, col, QTableWidgetItem(COORD_FORMAT_NA))

            self.window_xy = {}
            self.frame_xy = {}

        self.target_found = found

    def _get_window_coords(self) -> Dict:
        """Callback to provide window coordinates to mouse tracker."""
        return self.window_xy

    def _get_frame_coords(self) -> Dict:
        """Callback to provide frame coordinates to mouse tracker."""
        return self.frame_xy

    def _on_mouse_position_changed(self, position_info: Dict) -> None:
        """Handle mouse position updates from mouse tracker."""
        if self.frozen:
            return

        try:
            screen_x = position_info.get("screen_x", 0)
            screen_y = position_info.get("screen_y", 0)

            # Update Screen row
            self.mouse_table.setItem(0, 0, QTableWidgetItem(f"{screen_x}, {screen_y}"))

            # Get pixel color for current position
            hex_color, rgb_color = self._get_pixel_color(screen_x, screen_y)

            # Update Window row
            if position_info.get("inside_window", False):
                window_x_percent = position_info.get("window_x_percent", 0)
                window_y_percent = position_info.get("window_y_percent", 0)
                self.mouse_table.setItem(1, 0, QTableWidgetItem(f"{screen_x}, {screen_y}"))
                self.mouse_table.setItem(1, 1, QTableWidgetItem(f"{window_x_percent:.2f}%, {window_y_percent:.2f}%"))
            else:
                self.mouse_table.setItem(1, 0, QTableWidgetItem(COORD_FORMAT_OUTSIDE))
                self.mouse_table.setItem(1, 1, QTableWidgetItem(COORD_FORMAT_NA))

            # Update Frame row
            self._update_frame_coordinates(position_info, screen_x, screen_y)

            # Update Color row
            self.mouse_table.setItem(3, 0, QTableWidgetItem(hex_color))
            self.mouse_table.setItem(3, 1, QTableWidgetItem(rgb_color))

        except Exception as e:
            self.logger.error(f"Error updating mouse display: {e}")
            self._reset_mouse_table_to_error()

    def _update_frame_coordinates(self, position_info: Dict, screen_x: int, screen_y: int) -> None:
        """Update frame coordinate display."""
        if position_info.get("inside_window", False):
            if position_info.get("inside_frame", False):
                frame_x = position_info.get("frame_x", 0)
                frame_y = position_info.get("frame_y", 0)
                x_percent = position_info.get("x_percent", 0)
                y_percent = position_info.get("y_percent", 0)
                self.mouse_table.setItem(2, 0, QTableWidgetItem(f"{frame_x}, {frame_y}"))
                self.mouse_table.setItem(2, 1, QTableWidgetItem(f"{x_percent:.2f}%, {y_percent:.2f}%"))
            else:
                # Inside window but outside frame - show clamped coordinates
                if self.frame_xy:
                    frame_x_raw = screen_x - self.frame_xy.get("x", 0)
                    frame_y_raw = screen_y - self.frame_xy.get("y", 0)
                    frame_width = self.frame_xy.get("width", 1)
                    frame_height = self.frame_xy.get("height", 1)

                    # Clamp to frame bounds
                    frame_x = max(0, min(frame_x_raw, frame_width))
                    frame_y = max(0, min(frame_y_raw, frame_height))

                    # Clamp percentages
                    x_percent = max(0.0, min(100.0, 100 * frame_x_raw / max(1, frame_width)))
                    y_percent = max(0.0, min(100.0, 100 * frame_y_raw / max(1, frame_height)))

                    self.mouse_table.setItem(2, 0, QTableWidgetItem(f"{frame_x}, {frame_y}"))
                    self.mouse_table.setItem(2, 1, QTableWidgetItem(f"{x_percent:.2f}%, {y_percent:.2f}%"))
                else:
                    self.mouse_table.setItem(2, 0, QTableWidgetItem(COORD_FORMAT_OUTSIDE))
                    self.mouse_table.setItem(2, 1, QTableWidgetItem(COORD_FORMAT_NA))
        else:
            self.mouse_table.setItem(2, 0, QTableWidgetItem(COORD_FORMAT_OUTSIDE))
            self.mouse_table.setItem(2, 1, QTableWidgetItem(COORD_FORMAT_NA))

    def _get_pixel_color(self, x: int, y: int) -> tuple[str, str]:
        """Get pixel color at specified coordinates."""
        try:
            import pyautogui

            pixel = pyautogui.pixel(x, y)
            if isinstance(pixel, tuple) and len(pixel) >= 3:
                r, g, b = pixel[:3]
                hex_color = f"#{r:02x}{g:02x}{b:02x}"
                rgb_color = f"{r}, {g}, {b}"
                return hex_color, rgb_color
        except Exception:
            pass
        return "#000000", "0, 0, 0"

    def _reset_mouse_table_to_error(self) -> None:
        """Reset mouse table to error state."""
        for row in range(4):
            for col in range(2):
                self.mouse_table.setItem(row, col, QTableWidgetItem(COORD_FORMAT_ERROR))

    def on_cell_clicked(self, row: int, column: int) -> None:
        """Handle cell clicks to copy values to clipboard."""
        try:
            import pyperclip

            item = self.mouse_table.item(row, column)
            if not item:
                return

            text = item.text()
            if not text or text in [COORD_FORMAT_NA, COORD_FORMAT_OUTSIDE, COORD_FORMAT_ERROR]:
                return

            # Copy to clipboard
            pyperclip.copy(text)
            self.logger.info(f"Copied to clipboard: {text}")
            self._show_copy_feedback(text)

        except Exception as e:
            self.logger.error(f"Failed to copy to clipboard: {e}")

    def _take_screenshot(self) -> None:
        """Take screenshot of frame area and open viewer."""
        if not self.frame_xy:
            self.logger.warning("No frame area available for screenshot")
            return

        try:
            from PIL import ImageGrab

            frame_x = self.frame_xy.get("x", 0)
            frame_y = self.frame_xy.get("y", 0)
            frame_width = self.frame_xy.get("width", 0)
            frame_height = self.frame_xy.get("height", 0)

            if frame_width <= 0 or frame_height <= 0:
                self.logger.warning("Invalid frame dimensions for screenshot")
                return

            # Take screenshot
            bbox = (frame_x, frame_y, frame_x + frame_width, frame_y + frame_height)
            screenshot = ImageGrab.grab(bbox=bbox, all_screens=True)

            # Open screenshot viewer
            viewer = ScreenshotViewer(self.frame_xy.copy(), screenshot)
            viewer.show()

            # Keep reference to prevent garbage collection
            self._screenshot_viewers.append(viewer)

            self.logger.info(f"Screenshot taken: {frame_width}x{frame_height} at ({frame_x}, {frame_y})")

        except Exception as e:
            self.logger.error(f"Failed to take screenshot: {e}")

    def keyPressEvent(self, event) -> None:
        """Handle key press events."""
        if event.key() == Qt.Key.Key_F and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            # Toggle freeze state
            self.frozen = not self.frozen
            freeze_status = "FROZEN" if self.frozen else "TRACKING"

            self.logger.info(f"Coordinate tracking {'frozen' if self.frozen else 'resumed'}")

            # Visual feedback
            original_title = self.windowTitle()
            self.setWindowTitle(f"{APP_TITLE} - {freeze_status}")
            QTimer.singleShot(1500, lambda: self.setWindowTitle(original_title))
        else:
            super().keyPressEvent(event)

    def _show_copy_feedback(self, copied_text: str) -> None:
        """Show visual feedback for clipboard copy."""
        original_title = self.windowTitle()
        original_text = self.title_label.text()

        # Update displays
        self.setWindowTitle(f"{APP_TITLE} - Copied: {copied_text}")
        self.title_label.setText(f"Copied: {copied_text}")

        # Flash green
        self._show_title_copied_feedback()

        # Restore after delay
        QTimer.singleShot(TIMER_FEEDBACK_DURATION, lambda: self.setWindowTitle(original_title))
        QTimer.singleShot(TIMER_FEEDBACK_DURATION, lambda: self.title_label.setText(original_text))

    def _show_title_copied_feedback(self) -> None:
        """Flash title label green."""
        self.title_label.setStyleSheet(f"""
            QLabel {{
                color: {COLOR_TEXT_PRIMARY};
                padding: 8px;
                background-color: {COLOR_ACCENT_GREEN};
                border-radius: 4px;
                margin-bottom: 4px;
            }}
        """)
        QTimer.singleShot(TIMER_FEEDBACK_DURATION, self._reset_title_label_style)

    def _reset_title_label_style(self) -> None:
        """Reset title label to normal style."""
        self.title_label.setStyleSheet(f"""
            QLabel {{
                color: {COLOR_TEXT_PRIMARY};
                padding: 8px;
                background-color: {COLOR_BACKGROUND_TERTIARY};
                border-radius: 4px;
                margin-bottom: 4px;
            }}
        """)

    def _restart_application(self) -> None:
        """Restart the application."""
        try:
            self.logger.info("Restarting application...")

            if getattr(sys, "frozen", False):
                executable = sys.executable
                args = [executable] + sys.argv[1:]
            else:
                executable = sys.executable
                args = [executable, __file__] + sys.argv[1:]

            self.close()
            subprocess.Popen(args, cwd=os.getcwd())
            QApplication.quit()

        except Exception as e:
            self.logger.error(f"Failed to restart application: {e}")

    def closeEvent(self, event) -> None:
        """Clean up on close."""
        if hasattr(self, "mouse_tracker"):
            self.mouse_tracker.stop_tracking()
        super().closeEvent(event)
