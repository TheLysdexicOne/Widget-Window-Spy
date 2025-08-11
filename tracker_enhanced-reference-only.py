#!/usr/bin/env python3
"""
Widget Automation Tool - Standalone Tracker Application

Single-file tracker window with coordinate monitoring and process tracking.
All required utilities are included below. No external imports except PyQt6 and standard library.
"""

import argparse
import ctypes
import io
import logging
import os
import pyautogui
import pyperclip
import re
import signal
import subprocess
import sys
from typing import Callable, Dict, Optional
from PIL import Image, ImageGrab

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal, QPoint, QRectF
from PyQt6.QtGui import (
    QAction,
    QFont,
    QPen,
    QPixmap,
    QBrush,
    QColor,
    QCursor,
    QWheelEvent,
    QMouseEvent,
    QKeyEvent,
)
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
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPixmapItem,
    QGraphicsItemGroup,
    QGraphicsLineItem,
    QFrame,
    QLineEdit,
    QGraphicsEllipseItem,
    QGraphicsRectItem,
)


# --- Utility: Window Detection ---
def find_target_window(target_process: str) -> Optional[Dict]:
    """Find the target window and its geometry. Returns info dict or None."""
    try:
        import psutil
        import win32gui
        import win32process
    except ImportError:
        return None

    # Ultra-fast: enumerate windows, match by title, then get PID
    target_pids = []

    def enum_windows_callback(hwnd, _):
        try:
            title = win32gui.GetWindowText(hwnd)
            if "WidgetInc" in title and win32gui.IsWindowVisible(hwnd):
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid not in target_pids:
                    target_pids.append(pid)
        except Exception:
            pass
        return True

    win32gui.EnumWindows(enum_windows_callback, None)

    # Find first valid process
    for pid in target_pids:
        try:
            proc = psutil.Process(pid)
            if proc.is_running() and proc.name() == target_process:
                # Find window for this PID
                def enum_windows_proc(hwnd, windows):
                    try:
                        _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
                        if window_pid == pid and win32gui.IsWindowVisible(hwnd):
                            title = win32gui.GetWindowText(hwnd)
                            if "WidgetInc" in title:
                                windows.append(hwnd)
                    except Exception:
                        pass
                    return True

                windows = []
                win32gui.EnumWindows(enum_windows_proc, windows)
                if windows:
                    hwnd = windows[0]
                    rect = win32gui.GetWindowRect(hwnd)
                    client_rect = win32gui.GetClientRect(hwnd)
                    client_left_top = win32gui.ClientToScreen(hwnd, (client_rect[0], client_rect[1]))
                    client_right_bottom = win32gui.ClientToScreen(hwnd, (client_rect[2], client_rect[3]))
                    client_x = client_left_top[0]
                    client_y = client_left_top[1]
                    client_w = client_right_bottom[0] - client_left_top[0]
                    client_h = client_right_bottom[1] - client_left_top[1]
                    title = win32gui.GetWindowText(hwnd)

                    # Calculate 3:2 aspect ratio frame area
                    target_ratio = 3.0 / 2.0
                    client_ratio = client_w / client_h if client_h else 1

                    if client_ratio > target_ratio:
                        # Client is wider than 3:2 - fit height, center width
                        frame_height = client_h
                        frame_width = int(frame_height * target_ratio)
                        px = client_x + (client_w - frame_width) // 2
                        py = client_y
                    else:
                        # Client is taller than 3:2 - fit width, center height
                        frame_width = client_w
                        frame_height = int(frame_width / target_ratio)
                        px = client_x
                        py = client_y + (client_h - frame_height) // 2

                    frame_area = {"x": px, "y": py, "width": frame_width, "height": frame_height}

                    # Refine frame borders using PyAutoGUI for better accuracy
                    refined_frame = _refine_frame_borders_pyautogui(frame_area)
                    refinement_applied = False
                    if refined_frame and refined_frame != frame_area:
                        frame_area = refined_frame
                        refinement_applied = True

                    return {
                        "pid": pid,
                        "window_info": {
                            "hwnd": hwnd,
                            "title": title,
                            "window_rect": rect,
                            "client_left": client_x,
                            "client_top": client_y,
                            "client_width": client_w,
                            "client_height": client_h,
                        },
                        "frame_area": frame_area,
                        "refinement_applied": refinement_applied,
                    }
        except Exception:
            continue
    return None


def _refine_frame_borders_pyautogui(frame_area: Dict) -> Optional[Dict]:
    """
    Refine frame borders using PyAutoGUI pixel checking.
    Adjusts left and right borders by ±1 or ±2 pixels to achieve exactly 2054 pixel width.
    """
    if not frame_area:
        return None

    x = frame_area.get("x", 0)
    y = frame_area.get("y", 0)
    width = frame_area.get("width", 0)
    height = frame_area.get("height", 0)

    # Only refine if width is close to target (within ±10 pixels)
    target_width = 2054
    if abs(width - target_width) > 10:
        return None

    try:
        # Use middle Y coordinate for validation (with buffer for overlay)
        validation_y = y + height // 2

        # Check if we need adjustment
        width_diff = target_width - width

        if width_diff == 0:
            return frame_area  # Already perfect

        # For the specific case where width=2053 and we need 2054,
        # PIL analysis shows the correct answer is to expand right (keep x, increase width)
        if width == 2053 and target_width == 2054:
            return {"x": x, "y": y, "width": target_width, "height": height}

        # Try adjustments: ±1 or ±2 pixels on left/right borders
        adjustments = []

        if abs(width_diff) <= 4:  # Can be fixed with ±2 pixel adjustments
            if width_diff > 0:  # Need to increase width
                # Try expanding right first (preserves X position), then left, then both
                adjustments = [
                    (0, width_diff),  # Expand right only (preserves X)
                    (-width_diff, 0),  # Expand left only
                    (-width_diff // 2, width_diff // 2 + width_diff % 2),  # Expand both
                ]
            else:  # Need to decrease width
                width_diff = abs(width_diff)
                # Try contracting right first (preserves X position), then left, then both
                adjustments = [
                    (0, -width_diff),  # Contract right only (preserves X)
                    (width_diff, 0),  # Contract left only
                    (width_diff // 2, -(width_diff // 2 + width_diff % 2)),  # Contract both
                ]

        # Test each adjustment
        for i, (left_adj, right_adj) in enumerate(adjustments):
            new_x = x + left_adj
            new_width = width - left_adj + right_adj

            if new_width == target_width:
                # Validate borders using pixel checking
                left_x = new_x - 1
                right_x = new_x + new_width

                # Check if we can safely sample these pixels (multi-monitor aware)
                if left_x >= -3840 and right_x < 7680:  # Wide multi-monitor bounds
                    try:
                        # Sample pixels to validate border
                        left_pixel = pyautogui.pixel(left_x, validation_y)
                        right_pixel = pyautogui.pixel(right_x, validation_y)

                        # Basic validation: borders should be different from typical game content
                        # (This is a simple heuristic - could be improved)
                        if left_pixel != right_pixel:  # Different colors suggest border area
                            return {"x": new_x, "y": y, "width": new_width, "height": height}
                    except Exception:
                        continue  # Try next adjustment

        # If no adjustment worked, return original
        return frame_area

    except Exception:
        # If any error occurs, return original frame area
        return frame_area


# --- Coordinate System Manager ---
class CoordinateSystem:
    """Simple coordinate system for frame area management."""

    def __init__(self):
        self.frame_area = None

    def update_frame_area(self, frame_area: Dict):
        """Update frame area."""
        self.frame_area = frame_area

    def is_inside_frame(self, screen_x: int, screen_y: int) -> bool:
        """Check if screen coordinates are inside the frame area."""
        if not self.frame_area:
            return False

        px = self.frame_area.get("x", 0)
        py = self.frame_area.get("y", 0)
        pw = self.frame_area.get("width", 0)
        ph = self.frame_area.get("height", 0)

        return px <= screen_x <= px + pw and py <= screen_y <= py + ph


# --- Utility: Mouse Tracker ---
class MouseTracker(QObject):
    position_changed = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self._window_xy_cb: Optional[Callable[[], Dict]] = None
        self._frame_xy_cb: Optional[Callable[[], Dict]] = None
        self._timer: Optional[QTimer] = None
        self.coord_system = CoordinateSystem()  # Coordinate system
        self.last_position_info = {}  # Store last position info

    def set_coordinate_callbacks(self, window_cb: Callable[[], Dict], frame_cb: Callable[[], Dict]):
        self._window_xy_cb = window_cb
        self._frame_xy_cb = frame_cb

    def start_tracking(self, interval_ms: int = 100):
        if self._timer is None:
            self._timer = QTimer()
            self._timer.timeout.connect(self._emit_position)
            self._timer.start(interval_ms)

    def _emit_position(self):
        pos_info = self._get_position_info()
        self.last_position_info = pos_info  # Store for clipboard access
        self.position_changed.emit(pos_info)

    def _get_position_info(self) -> Dict:
        # Get mouse position using ctypes
        try:

            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

            pt = POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            screen_x, screen_y = pt.x, pt.y
        except Exception:
            screen_x, screen_y = 0, 0

        info = {"screen_x": screen_x, "screen_y": screen_y}

        # Window info
        if self._window_xy_cb:
            win_info = self._window_xy_cb()
            if win_info and "window_rect" in win_info:
                wx1, wy1, wx2, wy2 = win_info["window_rect"]
                if wx1 <= screen_x <= wx2 and wy1 <= screen_y <= wy2:
                    info["inside_window"] = True
                    info["window_x_percent"] = 100 * (screen_x - wx1) / max(1, wx2 - wx1)
                    info["window_y_percent"] = 100 * (screen_y - wy1) / max(1, wy2 - wy1)
                else:
                    info["inside_window"] = False

        # Frame info
        if self._frame_xy_cb:
            frame = self._frame_xy_cb()
            if frame:
                # Update coordinate system with current frame
                self.coord_system.update_frame_area(frame)

                # Only calculate percentages if mouse is inside frame area
                if self.coord_system.is_inside_frame(screen_x, screen_y):
                    info["inside_frame"] = True

                    # Calculate actual pixel coordinates within frame area
                    px = frame.get("x", 0)
                    py = frame.get("y", 0)
                    pw = frame.get("width", 0)
                    ph = frame.get("height", 0)

                    rel_x = screen_x - px
                    rel_y = screen_y - py
                    info["frame_x"] = rel_x
                    info["frame_y"] = rel_y

                    info["x_percent"] = 100 * rel_x / max(1, pw)
                    info["y_percent"] = 100 * rel_y / max(1, ph)
                else:
                    info["inside_frame"] = False

        return info


# --- Screenshot Viewer Window ---
class ScreenshotViewer(QGraphicsView):
    """Complete screenshot viewer with banners, zoom, pan, grid, and coordinate copying."""

    def __init__(self, frame_area: Dict, screenshot: Image.Image):
        super().__init__()
        self.frame_area = frame_area
        self.screenshot = screenshot

        # QGraphicsView setup
        self._zoom = 0
        self._empty = True
        self._scene = QGraphicsScene(self)
        self._photo = QGraphicsPixmapItem()
        self._photo.setShapeMode(QGraphicsPixmapItem.ShapeMode.BoundingRectShape)
        self._scene.addItem(self._photo)
        self.setScene(self._scene)

        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QBrush(QColor(30, 30, 30)))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        # Grid overlay
        self.show_grid = False
        self._grid_item = None

        # Locate functionality
        self.locate_items = []  # Store locate animation items
        self.locate_state = 0  # 0=none, 1=animation, 2=box, 3=none
        self.locate_timer = QTimer()
        self.locate_timer.timeout.connect(self._update_locate_animation)
        self.locate_animation_step = 0

        # Draw BBOX functionality
        self.draw_bbox_mode = False
        self.bbox_rect_item = None
        self.bbox_handles = []  # Handle items for resizing
        self.bbox_dragging = False
        self.bbox_resizing = False
        self.bbox_resize_handle = None
        self.bbox_last_pos = None

        # Simple click detection
        self._mouse_pressed_pos = QPoint()
        self._last_copied = "----, ----"

        # Convert PIL Image to QPixmap and set photo
        self.original_pixmap = self._pil_to_qpixmap(screenshot)
        self.setPhoto(self.original_pixmap)

        # Setup window as a standalone widget
        self._setup_as_window()

    def _pil_to_qpixmap(self, pil_image: Image.Image) -> QPixmap:
        """Convert PIL Image to QPixmap."""
        buffer = io.BytesIO()
        pil_image.save(buffer, format="PNG")
        buffer.seek(0)
        pixmap = QPixmap()
        pixmap.loadFromData(buffer.getvalue())
        return pixmap

    def _setup_as_window(self):
        """Setup this QGraphicsView as a standalone window with banners."""
        # Create a wrapper widget to hold banners + this view
        self.window_widget = QWidget()
        self.window_widget.setWindowTitle("Frame Screenshot Viewer")
        self.window_widget.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.window_widget.resize(1280, 720)
        self.window_widget.setMinimumSize(800, 600)
        self.window_widget.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
            }
        """)

        layout = QVBoxLayout(self.window_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Banner styling template
        banner_style = """
            QLabel {
                background-color: #2d2d2d;
                color: #ffffff;
                padding: 2px 4px;
                border-bottom: none;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12pt;
            }
        """

        # Line 1: Frame info + stretch + Draw BBOX button
        self.header_line1 = QWidget()
        # self.header_line1.setFixedHeight(24)
        self.header_line1.setStyleSheet("QWidget { background-color: #2d2d2d; }")
        line1_layout = QHBoxLayout(self.header_line1)
        line1_layout.setContentsMargins(2, 1, 2, 1)

        self.frame_info_label = QLabel()
        self.frame_info_label.setStyleSheet(banner_style)

        # Draw BBOX button
        self.draw_bbox_button = QPushButton("Draw BBOX")
        self.draw_bbox_button.setFixedWidth(80)
        self.draw_bbox_button.clicked.connect(self._on_draw_bbox_clicked)
        self.draw_bbox_button.setStyleSheet("""
            QPushButton {
                background-color: #388e3c;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 2px;
                font-weight: bold;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #4caf50;
            }
            QPushButton:pressed {
                background-color: #2e7d32;
            }
        """)

        line1_layout.addWidget(self.frame_info_label)
        line1_layout.addStretch()
        line1_layout.addWidget(self.draw_bbox_button)

        # Line 2: Copied info + input box
        self.header_line2 = QWidget()
        # self.header_line2.setFixedHeight(24)
        self.header_line2.setStyleSheet("QWidget { background-color: #2d2d2d; border-bottom: 1px solid #555555; }")
        line2_layout = QHBoxLayout(self.header_line2)
        line2_layout.setContentsMargins(2, 1, 2, 1)

        self.locate_text_label = QLabel("LOCATE:")
        self.locate_text_label.setStyleSheet(banner_style + "QLabel { font-weight: bold; }")

        self.copied_info_label = QLabel()
        self.copied_info_label.setStyleSheet(banner_style)

        self.coord_input = QLineEdit()
        self.coord_input.setPlaceholderText("100,200 or 0.5,0.75 or 10,20,30,40")
        self.coord_input.setFixedWidth(200)
        self.coord_input.setStyleSheet("""
            QLineEdit {
                background-color: #3d3d3d;
                color: #ffffff;
                border: 1px solid #555;
                padding: 2px 5px;
                font-size: 9pt;
            }
        """)

        line2_layout.addWidget(self.copied_info_label)
        line2_layout.addStretch()
        line2_layout.addWidget(self.locate_text_label)
        line2_layout.addWidget(self.coord_input)

        # Line 3: Locate status + buttons
        self.header_line3 = QWidget()
        self.header_line3.setFixedHeight(32)
        self.header_line3.setStyleSheet("QWidget { background-color: #2d2d2d; border-bottom: 1px solid #555555; }")
        line3_layout = QHBoxLayout(self.header_line3)
        line3_layout.setContentsMargins(2, 1, 2, 1)

        self.locate_info_label = QLabel("Ready")
        self.locate_info_label.setStyleSheet(banner_style)

        # Buttons container
        buttons_widget = QWidget()
        buttons_layout = QHBoxLayout(buttons_widget)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(5)

        self.locate_button = QPushButton("LOCATE")
        self.locate_button.setFixedWidth(60)
        self.locate_button.clicked.connect(self._on_locate_clicked)
        self.locate_button.setStyleSheet("""
            QPushButton {
                background-color: #1976d2;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 2px;
                font-weight: bold;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #2196f3;
            }
            QPushButton:pressed {
                background-color: #0d47a1;
            }
        """)

        self.clear_button = QPushButton("CLEAR")
        self.clear_button.setFixedWidth(50)
        self.clear_button.clicked.connect(self._on_clear_clicked)
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: #666666;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 2px;
                font-weight: bold;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #777777;
            }
            QPushButton:pressed {
                background-color: #555555;
            }
        """)

        buttons_layout.addWidget(self.locate_button)
        buttons_layout.addWidget(self.clear_button)

        line3_layout.addWidget(self.locate_info_label)
        line3_layout.addStretch()
        line3_layout.addWidget(buttons_widget)

        # Footer - simplified
        self.footer_banner = QLabel()
        self.footer_banner.setFixedHeight(24)
        self.footer_banner.setStyleSheet("""
            QLabel {
                background-color: #2d2d2d;
                color: #888888;
                padding: 4px 10px;
                border-top: 1px solid #555555;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
                font-style: italic;
            }
        """)

        layout.addWidget(self.header_line1)
        layout.addWidget(self.header_line2)
        layout.addWidget(self.header_line3)
        layout.addWidget(self)  # Add this QGraphicsView to the layout
        layout.addWidget(self.footer_banner)

        self._update_info_banner()
        self._update_footer_banner()  # Initialize footer
        self.window_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def show(self):
        """Show the window widget."""
        self.window_widget.show()

    def hasPhoto(self):
        return not self._empty

    def resetView(self, scale=1):
        rect = QRectF(self._photo.pixmap().rect())
        if not rect.isNull():
            overpan_pixels = 75
            expanded_rect = rect.adjusted(-overpan_pixels, -overpan_pixels, overpan_pixels, overpan_pixels)
            self.setSceneRect(expanded_rect)

            if (scale := max(1, scale)) == 1:
                self._zoom = 0
            if self.hasPhoto():
                unity = self.transform().mapRect(QRectF(0, 0, 1, 1))
                self.scale(1 / unity.width(), 1 / unity.height())
                viewport = self.viewport()
                if viewport:
                    viewrect = viewport.rect()
                    scenerect = self.transform().mapRect(rect)
                    factor = min(viewrect.width() / scenerect.width(), viewrect.height() / scenerect.height()) * scale
                    self.scale(factor, factor)
                    self.centerOn(self._photo)

    def setPhoto(self, pixmap=None):
        if pixmap and not pixmap.isNull():
            self._empty = False
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self._photo.setPixmap(pixmap)
            rect = QRectF(pixmap.rect())
            overpan_pixels = 75
            expanded_rect = rect.adjusted(-overpan_pixels, -overpan_pixels, overpan_pixels, overpan_pixels)
            self.setSceneRect(expanded_rect)
        else:
            self._empty = True
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self._photo.setPixmap(QPixmap())
        self._zoom = 0
        self.resetView()

    def zoom(self, step):
        scale_factor = 1.25
        zoom = max(0, self._zoom + (step := int(step)))
        if zoom != self._zoom:
            self._zoom = zoom
            if self._zoom > 0:
                if step > 0:
                    factor = scale_factor**step
                else:
                    factor = 1 / scale_factor ** abs(step)
                self.scale(factor, factor)
            else:
                self.resetView()
            self._update_grid()
            self._update_info_banner()  # Update zoom info immediately

    def wheelEvent(self, event: QWheelEvent):
        if self.hasPhoto():
            delta = event.angleDelta().y()
            self.zoom(delta and delta // abs(delta))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.hasPhoto():
            self.resetView()

    def updateCoordinates(self, pos=None):
        """Update coordinate display in banner."""
        if self._photo.isUnderMouse():
            if pos is None:
                pos = self.mapFromGlobal(QCursor.pos())
            scene_pos = self.mapToScene(pos)
            point = QPoint(int(scene_pos.x()), int(scene_pos.y()))
        else:
            point = QPoint()
        self._on_coordinates_changed(point)

    def _on_coordinates_changed(self, point):
        """Handle coordinate changes and update banner with unified coordinate display."""
        # Line 1: Current mouse coordinates only
        if not point.isNull():
            pixel_x = int(point.x())
            pixel_y = int(point.y())

            # Calculate all coordinate types
            frame_x = self.frame_area.get("x", 0)
            frame_y = self.frame_area.get("y", 0)
            frame_width = self.frame_area.get("width", 1)
            frame_height = self.frame_area.get("height", 1)

            # Screen coordinates
            screen_x = frame_x + pixel_x
            screen_y = frame_y + pixel_y

            # Frame percentages
            x_percent = max(0, min(100, (pixel_x / frame_width) * 100))
            y_percent = max(0, min(100, (pixel_y / frame_height) * 100))

            coord_section = f" MOUSE || Screen Coords: {screen_x:>5}, {screen_y:>4} | Frame Coords: {pixel_x:>4}, {pixel_y:>4} | Frame %: {x_percent:>7.4f}%, {y_percent:>7.4f}%"
        else:
            coord_section = (
                " MOUSE || Screen Coords: -----, ---- | Frame Coords: ----, ---- | Frame %: --.----%, --.----%"
            )

        self.frame_info_label.setText(coord_section)

        # Line 2: Copied coordinates - translate the copied percentage back to all formats
        copied_section = self._get_copied_coordinates_display()
        self.copied_info_label.setText(copied_section)

        # Line 3: Show locate coordinates in same format when active, or blank when not locating
        locate_section = self._get_locate_coordinates_display()
        self.locate_info_label.setText(locate_section)

    def _get_copied_coordinates_display(self):
        """Convert the last copied percentage back to all coordinate formats for display."""
        # Parse the copied coordinates (can be "x, y" as frame pixels or "x1,y1,x2,y2" as bbox)
        try:
            parts = self._last_copied.replace(" ", "").split(",")
            if len(parts) == 2:
                # Single point coordinates
                copied_frame_x = int(parts[0])
                copied_frame_y = int(parts[1])

                # Calculate all coordinate types from the copied frame coordinates
                frame_x = self.frame_area.get("x", 0)
                frame_y = self.frame_area.get("y", 0)
                frame_width = self.frame_area.get("width", 1)
                frame_height = self.frame_area.get("height", 1)

                # Screen coordinates
                copied_screen_x = frame_x + copied_frame_x
                copied_screen_y = frame_y + copied_frame_y

                # Frame percentages
                copied_x_percent = max(0, min(100, (copied_frame_x / frame_width) * 100))
                copied_y_percent = max(0, min(100, (copied_frame_y / frame_height) * 100))

                return f"COPIED || Screen Coords: {copied_screen_x:>5}, {copied_screen_y:>4} | Frame Coords: {copied_frame_x:>4}, {copied_frame_y:>4} | Frame %: {copied_x_percent:>7.4f}%, {copied_y_percent:>7.4f}%"

            elif len(parts) == 4:
                # Bbox coordinates
                x1, y1, x2, y2 = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])

                # Calculate screen coordinates for bbox
                frame_x = self.frame_area.get("x", 0)
                frame_y = self.frame_area.get("y", 0)

                screen_x1 = frame_x + x1
                screen_y1 = frame_y + y1
                screen_x2 = frame_x + x2
                screen_y2 = frame_y + y2

                return f"COPIED || BBOX: Frame({x1:>4},{y1:>4},{x2:>4},{y2:>4}) | Screen({screen_x1:>4},{screen_y1:>4},{screen_x2:>4},{screen_y2:>4})"

            else:
                return "COPIED || Screen Coords: -----, ---- | Frame Coords: ----, ---- | Frame %:  --.----%, --.----%"
        except Exception:
            return "COPIED || Screen Coords: -----, ---- | Frame Coords: ----, ---- | Frame %: --.----%, --.----%"

    def _get_locate_coordinates_display(self):
        """Display locate coordinates in the same format as mouse/copied coordinates."""
        if hasattr(self, "target_x") and hasattr(self, "target_y") and self.locate_state > 0:
            # Calculate all coordinate types from the locate target coordinates
            frame_x = self.frame_area.get("x", 0)
            frame_y = self.frame_area.get("y", 0)
            frame_width = self.frame_area.get("width", 1)
            frame_height = self.frame_area.get("height", 1)

            # Screen coordinates
            locate_screen_x = frame_x + int(self.target_x)
            locate_screen_y = frame_y + int(self.target_y)

            # Frame percentages
            locate_x_percent = max(0, min(100, (self.target_x / frame_width) * 100))
            locate_y_percent = max(0, min(100, (self.target_y / frame_height) * 100))

            return f"LOCATE || Screen Coords: {locate_screen_x:>5}, {locate_screen_y:>4} | Frame Coords: {int(self.target_x):>4}, {int(self.target_y):>4} | Frame %: {locate_x_percent:>7.4f}%, {locate_y_percent:>7.4f}%"
        else:
            return "LOCATE || Screen Coords: -----, ---- | Frame Coords: ----, ---- | Frame %: --.----%, --.----%"

    def _update_footer_banner(self):
        """Update the footer banner with instructions, frame info, and grid/zoom info."""
        frame_size_section = f"Frame: {self.frame_area.get('x', 0):>4}, {self.frame_area.get('y', 0):>4} | Size: {self.frame_area.get('width', 0):>4}x{self.frame_area.get('height', 0):>4}"
        grid_zoom_section = f"Grid: {'ON ' if self.show_grid else 'OFF'} | Zoom: {self._zoom:>2}x"
        footer_text = f"Instructions: Mouse: Wheel=Zoom, Drag=Pan, Right=Grid, Left=Copy%, F=Fit                    {frame_size_section}                    {grid_zoom_section}"
        self.footer_banner.setText(footer_text)

    def _update_info_banner(self):
        """Update the information banner and footer."""
        self._on_coordinates_changed(QPoint())  # Update with null point
        self._update_footer_banner()  # Update footer too

    def mouseMoveEvent(self, event: QMouseEvent):
        # Handle bbox operations
        if self.draw_bbox_mode:
            scene_pos = self.mapToScene(event.position().toPoint())

            if self.bbox_dragging and self.bbox_rect_item is not None and self.bbox_last_pos is not None:
                # Move entire bbox with grid snapping
                delta = scene_pos - self.bbox_last_pos
                current_rect = self.bbox_rect_item.rect()

                # Apply grid snapping to the movement
                new_x = self._snap_to_grid(current_rect.x() + delta.x())
                new_y = self._snap_to_grid(current_rect.y() + delta.y())

                new_rect = QRectF(new_x, new_y, current_rect.width(), current_rect.height())
                self.bbox_rect_item.setRect(new_rect)
                self._create_resize_handles()  # Update handle positions
                self.bbox_last_pos = scene_pos

            elif (
                self.bbox_resizing
                and hasattr(self, "bbox_resize_direction")
                and self.bbox_last_pos is not None
                and self.bbox_rect_item is not None
            ):
                # Resize bbox based on direction with grid snapping
                direction = self.bbox_resize_direction
                delta = scene_pos - self.bbox_last_pos
                current_rect = self.bbox_rect_item.rect()

                new_rect = QRectF(current_rect)

                # Apply resize based on direction with grid snapping
                if "n" in direction:  # North (top)
                    new_top = self._snap_to_grid(current_rect.top() + delta.y())
                    new_rect.setTop(new_top)
                if "s" in direction:  # South (bottom)
                    new_bottom = self._snap_to_grid(current_rect.bottom() + delta.y())
                    new_rect.setBottom(new_bottom)
                if "w" in direction:  # West (left)
                    new_left = self._snap_to_grid(current_rect.left() + delta.x())
                    new_rect.setLeft(new_left)
                if "e" in direction:  # East (right)
                    new_right = self._snap_to_grid(current_rect.right() + delta.x())
                    new_rect.setRight(new_right)

                # Ensure minimum size
                min_size = 10
                if new_rect.width() >= min_size and new_rect.height() >= min_size:
                    self.bbox_rect_item.setRect(new_rect)
                    self._create_resize_handles()  # Update handle positions
                    self.bbox_last_pos = scene_pos
            else:
                # Not actively dragging/resizing - update cursor based on hover
                resize_direction = self._get_resize_direction_at_point(scene_pos)
                if resize_direction:
                    # Hovering over a handle - show resize cursor
                    cursor = self._get_resize_cursor(resize_direction)
                    self.setCursor(cursor)
                elif self.bbox_rect_item is not None and self.bbox_rect_item.contains(
                    self.bbox_rect_item.mapFromScene(scene_pos)
                ):
                    # Hovering over bbox center - show move cursor
                    self.setCursor(Qt.CursorShape.SizeAllCursor)
                else:
                    # Not hovering over bbox - show normal cursor
                    self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            # Not in bbox mode - ensure normal cursor
            self.setCursor(Qt.CursorShape.ArrowCursor)

        # Regular coordinate updating (only if not dragging bbox)
        if not (self.draw_bbox_mode and (self.bbox_dragging or self.bbox_resizing)):
            self.updateCoordinates(event.position().toPoint())
        super().mouseMoveEvent(event)

    def _on_draw_bbox_clicked(self):
        """Handle draw bbox button click."""
        self.draw_bbox_mode = not self.draw_bbox_mode
        if self.draw_bbox_mode:
            self.draw_bbox_button.setText("Done")
            self.draw_bbox_button.setStyleSheet("""
                QPushButton {
                    background-color: #1976d2;
                    color: white;
                    border: none;
                    padding: 4px 8px;
                    border-radius: 2px;
                    font-weight: bold;
                    font-size: 9pt;
                }
                QPushButton:hover {
                    background-color: #2196f3;
                }
                QPushButton:pressed {
                    background-color: #0d47a1;
                }
            """)
            # Create initial bbox in center of image
            self._create_initial_bbox()
        else:
            self.draw_bbox_button.setText("Draw BBOX")
            self.draw_bbox_button.setStyleSheet("""
                QPushButton {
                    background-color: #388e3c;
                    color: white;
                    border: none;
                    padding: 4px 8px;
                    border-radius: 2px;
                    font-weight: bold;
                    font-size: 9pt;
                }
                QPushButton:hover {
                    background-color: #4caf50;
                }
                QPushButton:pressed {
                    background-color: #2e7d32;
                }
            """)
            # Clear bbox and handles
            self._clear_bbox()

    def _create_initial_bbox(self):
        """Create initial 100x100 bbox in center of image."""
        if not self.hasPhoto():
            return

        pixmap = self._photo.pixmap()
        if pixmap.isNull():
            return

        # Calculate center position
        center_x = pixmap.width() / 2
        center_y = pixmap.height() / 2

        # Create 100x100 bbox centered
        bbox_size = 100
        left = center_x - bbox_size / 2
        top = center_y - bbox_size / 2

        # Create the main bbox rectangle
        self.bbox_rect_item = QGraphicsRectItem(left, top, bbox_size, bbox_size)
        pen = QPen(QColor(255, 255, 0))  # Yellow
        pen.setWidth(2)
        pen.setCosmetic(True)
        self.bbox_rect_item.setPen(pen)
        self.bbox_rect_item.setBrush(QBrush())  # No fill
        self._scene.addItem(self.bbox_rect_item)

        # Create resize handles
        self._create_resize_handles()

        # Update copied coordinates
        self._update_bbox_coordinates()

    def _create_resize_handles(self):
        """Create invisible edge handles for the entire bbox edges."""
        if not self.bbox_rect_item:
            return

        # Clear existing handles
        for handle in self.bbox_handles:
            self._scene.removeItem(handle)
        self.bbox_handles.clear()

        rect = self.bbox_rect_item.rect()

        # Get current zoom scale for proper handle sizing
        transform = self.transform()
        scale_factor = max(0.5, transform.m11())  # Minimum scale factor
        handle_width = max(3, 6 / scale_factor)  # Scale inversely with zoom, min 3px

        # Create invisible edge handles that cover the entire edges
        # Top edge handle
        top_handle = QGraphicsRectItem(rect.left(), rect.top() - handle_width / 2, rect.width(), handle_width)
        top_handle.setPen(QPen(Qt.PenStyle.NoPen))  # Invisible
        top_handle.setBrush(QBrush())  # No fill
        top_handle.setData(0, "n")
        self._scene.addItem(top_handle)
        self.bbox_handles.append(top_handle)

        # Bottom edge handle
        bottom_handle = QGraphicsRectItem(rect.left(), rect.bottom() - handle_width / 2, rect.width(), handle_width)
        bottom_handle.setPen(QPen(Qt.PenStyle.NoPen))  # Invisible
        bottom_handle.setBrush(QBrush())  # No fill
        bottom_handle.setData(0, "s")
        self._scene.addItem(bottom_handle)
        self.bbox_handles.append(bottom_handle)

        # Left edge handle
        left_handle = QGraphicsRectItem(rect.left() - handle_width / 2, rect.top(), handle_width, rect.height())
        left_handle.setPen(QPen(Qt.PenStyle.NoPen))  # Invisible
        left_handle.setBrush(QBrush())  # No fill
        left_handle.setData(0, "w")
        self._scene.addItem(left_handle)
        self.bbox_handles.append(left_handle)

        # Right edge handle
        right_handle = QGraphicsRectItem(rect.right() - handle_width / 2, rect.top(), handle_width, rect.height())
        right_handle.setPen(QPen(Qt.PenStyle.NoPen))  # Invisible
        right_handle.setBrush(QBrush())  # No fill
        right_handle.setData(0, "e")
        self._scene.addItem(right_handle)
        self.bbox_handles.append(right_handle)

    def _clear_bbox(self):
        """Clear bbox and all handles."""
        if self.bbox_rect_item:
            self._scene.removeItem(self.bbox_rect_item)
            self.bbox_rect_item = None

        for handle in self.bbox_handles:
            self._scene.removeItem(handle)
        self.bbox_handles.clear()

        self.bbox_dragging = False
        self.bbox_resizing = False
        if hasattr(self, "bbox_resize_direction"):
            delattr(self, "bbox_resize_direction")

        # Reset cursor to normal
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def _update_bbox_coordinates(self):
        """Update copied coordinates from current bbox position."""
        if not self.bbox_rect_item:
            return

        rect = self.bbox_rect_item.rect()
        x1, y1 = int(rect.left()), int(rect.top())
        x2, y2 = int(rect.right()), int(rect.bottom())

        # Copy bbox coordinates
        bbox_text = f"{x1},{y1},{x2},{y2}"
        pyperclip.copy(bbox_text)

        # Update display
        self._last_copied = f"{x1},{y1},{x2},{y2}"
        self._update_info_banner()

    def _get_resize_cursor(self, direction):
        """Get the appropriate cursor for a resize direction."""
        cursor_map = {
            "nw": Qt.CursorShape.SizeFDiagCursor,  # Top-left diagonal
            "ne": Qt.CursorShape.SizeBDiagCursor,  # Top-right diagonal
            "sw": Qt.CursorShape.SizeBDiagCursor,  # Bottom-left diagonal
            "se": Qt.CursorShape.SizeFDiagCursor,  # Bottom-right diagonal
            "n": Qt.CursorShape.SizeVerCursor,  # Vertical
            "s": Qt.CursorShape.SizeVerCursor,  # Vertical
            "w": Qt.CursorShape.SizeHorCursor,  # Horizontal
            "e": Qt.CursorShape.SizeHorCursor,  # Horizontal
        }
        return cursor_map.get(direction, Qt.CursorShape.ArrowCursor)

    def _snap_to_grid(self, value, grid_size=1):
        """Snap a value to the nearest grid point."""
        return round(value / grid_size) * grid_size

    def _get_resize_direction_at_point(self, scene_pos):
        """Determine resize direction based on mouse position relative to bbox."""
        if not self.bbox_rect_item:
            return None

        rect = self.bbox_rect_item.rect()

        # Get current zoom scale for proper corner detection
        transform = self.transform()
        scale_factor = max(0.5, transform.m11())
        corner_threshold = max(8, 12 / scale_factor)  # Scale inversely with zoom

        # Check for corner proximity first (corners take priority)
        corners = [
            (rect.topLeft(), "nw"),
            (rect.topRight(), "ne"),
            (rect.bottomLeft(), "sw"),
            (rect.bottomRight(), "se"),
        ]

        for corner_point, direction in corners:
            distance = ((scene_pos.x() - corner_point.x()) ** 2 + (scene_pos.y() - corner_point.y()) ** 2) ** 0.5
            if distance <= corner_threshold:
                return direction

        # Check if clicking on edge handles
        for handle in self.bbox_handles:
            if handle.contains(handle.mapFromScene(scene_pos)):
                return handle.data(0)

        return None

    def mousePressEvent(self, event: QMouseEvent):
        if self.draw_bbox_mode and event.button() == Qt.MouseButton.LeftButton:
            if self.hasPhoto():
                scene_pos = self.mapToScene(event.position().toPoint())

                # Get resize direction (corners or edges)
                resize_direction = self._get_resize_direction_at_point(scene_pos)

                if resize_direction:
                    # Start resizing - disable view dragging
                    self.bbox_resizing = True
                    self.bbox_resize_direction = resize_direction  # Store direction directly
                    self.bbox_last_pos = scene_pos
                    self.setDragMode(QGraphicsView.DragMode.NoDrag)  # Disable panning during resize
                elif self.bbox_rect_item is not None and self.bbox_rect_item.contains(
                    self.bbox_rect_item.mapFromScene(scene_pos)
                ):
                    # Start dragging bbox
                    self.bbox_dragging = True
                    self.bbox_last_pos = scene_pos
                    # Disable view dragging while bbox dragging
                    self.setDragMode(QGraphicsView.DragMode.NoDrag)

        elif event.button() == Qt.MouseButton.RightButton:
            self.show_grid = not self.show_grid
            self._update_grid()
        elif event.button() == Qt.MouseButton.LeftButton and not self.draw_bbox_mode:
            self._mouse_pressed_pos = event.position().toPoint()

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self.draw_bbox_mode and event.button() == Qt.MouseButton.LeftButton:
            if self.bbox_dragging or self.bbox_resizing:
                # Update coordinates after drag/resize
                self._update_bbox_coordinates()

                # Reset states
                self.bbox_dragging = False
                self.bbox_resizing = False
                if hasattr(self, "bbox_resize_direction"):
                    delattr(self, "bbox_resize_direction")

                # Re-enable view dragging
                self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        elif event.button() == Qt.MouseButton.LeftButton and not self.draw_bbox_mode:
            release_pos = event.position().toPoint()
            delta = release_pos - self._mouse_pressed_pos

            # Simple click detection: ≤3 pixels movement = click
            if abs(delta.x()) <= 3 and abs(delta.y()) <= 3:
                if self.hasPhoto():
                    scene_pos = self.mapToScene(release_pos)
                    pixmap = self._photo.pixmap()
                    if not pixmap.isNull():
                        photo_rect = QRectF(0, 0, pixmap.width(), pixmap.height())
                        if photo_rect.contains(scene_pos):
                            self._copy_percentage_at_position(scene_pos)
        super().mouseReleaseEvent(event)

    def _copy_percentage_at_position(self, scene_pos):
        """Copy percentage coordinates at scene position."""
        frame_width = self.frame_area.get("width", 1)
        frame_height = self.frame_area.get("height", 1)

        x_percent = max(0, min(100, (scene_pos.x() / frame_width) * 100))
        y_percent = max(0, min(100, (scene_pos.y() / frame_height) * 100))

        # Format with 6 decimal precision and copy
        import pyperclip

        percentage_text = f"{x_percent / 100:.6f}, {y_percent / 100:.6f}"
        pyperclip.copy(percentage_text)

        # Update display
        pixel_x = int(scene_pos.x())
        pixel_y = int(scene_pos.y())
        self._last_copied = f"{pixel_x:>4}, {pixel_y:>4}"
        self._update_info_banner()

    def leaveEvent(self, event):
        self._on_coordinates_changed(QPoint())
        super().leaveEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_F:
            self.resetView()
            self._update_info_banner()
        else:
            super().keyPressEvent(event)

    def _update_grid(self):
        if self._grid_item:
            self._scene.removeItem(self._grid_item)
            self._grid_item = None

        if self.show_grid and self.hasPhoto():
            pixmap = self._photo.pixmap()
            if not pixmap.isNull():
                transform = self.transform()
                scale_factor = transform.m11()
                if scale_factor >= 0.5:
                    grid_item = self._create_pixel_grid(pixmap.width(), pixmap.height())
                    if grid_item:
                        self._grid_item = grid_item
                        self._scene.addItem(self._grid_item)

        # Update footer to reflect grid state
        self._update_footer_banner()

    def _create_pixel_grid(self, width, height):
        """Create a simple pixel grid."""
        grid_group = QGraphicsItemGroup()
        pen = QPen(QColor(0, 255, 255, 128))
        pen.setWidth(1)
        pen.setCosmetic(True)

        transform = self.transform()
        scale_factor = transform.m11()

        # Simple grid step calculation
        if scale_factor >= 8.0:
            step = 1
        elif scale_factor >= 4.0:
            step = 2
        elif scale_factor >= 2.0:
            step = 5
        else:
            step = 10

        # Create grid lines
        for x in range(0, width + 1, step):
            line = QGraphicsLineItem(x, 0, x, height)
            line.setPen(pen)
            grid_group.addToGroup(line)

        for y in range(0, height + 1, step):
            line = QGraphicsLineItem(0, y, width, y)
            line.setPen(pen)
            grid_group.addToGroup(line)

        return grid_group

    def _on_locate_clicked(self):
        """Handle locate button click."""
        try:
            coord_text = self.coord_input.text().strip()
            if not coord_text:
                self.locate_info_label.setText("Enter coordinates")
                return

            # Parse coordinates using regex to handle various formats
            parsed_data = self._parse_coordinates_regex(coord_text)
            if not parsed_data:
                return

            # Clear any existing locate items
            self._clear_locate()

            if parsed_data["type"] == "point":
                # Single point - start radar animation
                self.locate_state = 1
                self.locate_animation_step = 0
                self._start_locate_animation(parsed_data["x"], parsed_data["y"])

            elif parsed_data["type"] == "bbox":
                # Bounding box - draw rectangle immediately
                self._draw_bbox(parsed_data["x1"], parsed_data["y1"], parsed_data["x2"], parsed_data["y2"])
                self.locate_info_label.setText(
                    f"BBox: {parsed_data['x1']},{parsed_data['y1']} to {parsed_data['x2']},{parsed_data['y2']}"
                )

        except Exception as e:
            self.locate_info_label.setText(f"Error: {str(e)}")

    def _on_clear_clicked(self):
        """Handle clear button click."""
        self._clear_locate()
        self.locate_state = 0
        self.locate_button.setText("LOCATE")
        # Line 3 will be updated automatically through _get_locate_coordinates_display()

    def _parse_coordinates_regex(self, coord_text):
        """Parse coordinates using regex to handle multiple formats."""
        # Remove any extra whitespace and normalize delimiters
        coord_text = re.sub(r"\s+", " ", coord_text.strip())
        coord_text = coord_text.replace(" ", ",")

        # Split by comma and extract numbers
        parts = [part.strip() for part in coord_text.split(",") if part.strip()]

        try:
            if len(parts) == 2:
                # Two values - single point (x, y)
                x, y = float(parts[0]), float(parts[1])

                # Auto-detect coordinate type and convert to scene coordinates
                scene_x, scene_y = self._convert_to_scene_coords(x, y)

                return {"type": "point", "x": scene_x, "y": scene_y}

            elif len(parts) == 4:
                # Four values - bounding box (x1, y1, x2, y2)
                x1, y1, x2, y2 = float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3])

                # Convert all coordinates to scene coordinates
                scene_x1, scene_y1 = self._convert_to_scene_coords(x1, y1)
                scene_x2, scene_y2 = self._convert_to_scene_coords(x2, y2)

                return {"type": "bbox", "x1": scene_x1, "y1": scene_y1, "x2": scene_x2, "y2": scene_y2}
            else:
                self.locate_info_label.setText("Enter 2 values (x,y) or 4 values (x1,y1,x2,y2)")
                return None

        except ValueError:
            self.locate_info_label.setText("Invalid number format")
            return None

    def _convert_to_scene_coords(self, x, y):
        """Convert coordinates to scene coordinates with auto-detection."""
        # Auto-detect coordinate type based on values
        if 0 <= x <= 1.0 and 0 <= y <= 1.0:
            # Decimal percentages (0.0 - 1.0)
            frame_width = self.frame_area.get("width", 1)
            frame_height = self.frame_area.get("height", 1)
            scene_x = x * frame_width
            scene_y = y * frame_height
            coord_type = "Frame %"

        elif 0 <= x <= 100 and 0 <= y <= 100 and (x > 1.0 or y > 1.0):
            # Percentage format (0-100)
            frame_width = self.frame_area.get("width", 1)
            frame_height = self.frame_area.get("height", 1)
            scene_x = (x / 100.0) * frame_width
            scene_y = (y / 100.0) * frame_height
            coord_type = "Frame %"

        elif x >= 1000 or y >= 1000:
            # Likely screen coordinates (large values)
            frame_x = self.frame_area.get("x", 0)
            frame_y = self.frame_area.get("y", 0)
            scene_x = x - frame_x
            scene_y = y - frame_y
            coord_type = "Screen"

        else:
            # Assume frame coordinates
            scene_x = x
            scene_y = y
            coord_type = "Frame"

        # Update info label with detected type
        self.locate_info_label.setText(f"Locating {x}, {y} ({coord_type})")

        return scene_x, scene_y

    def _draw_bbox(self, x1, y1, x2, y2):
        """Draw a bounding box rectangle."""
        # Ensure proper ordering (top-left to bottom-right)
        left = min(x1, x2)
        top = min(y1, y2)
        right = max(x1, x2)
        bottom = max(y1, y2)

        width = right - left
        height = bottom - top

        # Create rectangle
        bbox_rect = QGraphicsRectItem(left, top, width, height)

        # Style the bounding box
        pen = QPen(QColor(255, 255, 0))  # Yellow
        pen.setWidth(2)
        pen.setCosmetic(True)
        bbox_rect.setPen(pen)
        bbox_rect.setBrush(QBrush())  # No fill

        self._scene.addItem(bbox_rect)
        self.locate_items.append(bbox_rect)

    def _start_locate_animation(self, target_x, target_y):
        """Start the radar ping animation."""
        self.target_x = target_x
        self.target_y = target_y

        # Check if target pixel is mostly white to choose color
        try:
            # Sample the target pixel color from the original screenshot
            if 0 <= int(target_x) < self.screenshot.width and 0 <= int(target_y) < self.screenshot.height:
                pixel_color = self.screenshot.getpixel((int(target_x), int(target_y)))
                # Check if pixel is mostly white (RGB values > 200)
                if isinstance(pixel_color, tuple) and len(pixel_color) >= 3:
                    is_white = all(c > 200 for c in pixel_color[:3])
                    self.locate_color = (
                        QColor(255, 255, 0) if is_white else QColor(255, 255, 255)
                    )  # Yellow if white, white otherwise
                else:
                    self.locate_color = QColor(255, 255, 255)  # Default white
            else:
                self.locate_color = QColor(255, 255, 255)  # Default white
        except Exception:
            self.locate_color = QColor(255, 255, 255)  # Default white

        self.locate_timer.start(100)  # Update every 100ms

    def _update_locate_animation(self):
        """Update the locate animation frame."""
        # Clear previous animation items
        for item in self.locate_items:
            self._scene.removeItem(item)
        self.locate_items.clear()

        # Animation: start from 50px radius and shrink down
        max_radius = 50
        total_steps = 20
        current_radius = max_radius - (self.locate_animation_step * max_radius / total_steps)

        if current_radius <= 1:
            # Animation complete - highlight the single pixel
            self._stop_locate_animation()
            self._highlight_single_pixel()
            return

        # Create circle at target location
        circle = QGraphicsEllipseItem(
            self.target_x - current_radius, self.target_y - current_radius, current_radius * 2, current_radius * 2
        )

        # Set pen for the circle
        pen = QPen(self.locate_color)
        pen.setWidth(2)
        pen.setCosmetic(True)
        circle.setPen(pen)
        circle.setBrush(QBrush())  # No fill

        self._scene.addItem(circle)
        self.locate_items.append(circle)

        self.locate_animation_step += 1

    def _stop_locate_animation(self):
        """Stop the locate animation."""
        self.locate_timer.stop()
        for item in self.locate_items:
            self._scene.removeItem(item)
        self.locate_items.clear()

    def _highlight_single_pixel(self):
        """Highlight the single target pixel at the end of animation."""
        # Create a 1x1 rectangle with solid fill and no border
        pixel_highlight = QGraphicsRectItem(self.target_x, self.target_y, 1, 1)

        # Use solid fill with no pen/border to highlight the exact pixel
        pixel_highlight.setPen(QPen(Qt.PenStyle.NoPen))  # No border
        pixel_highlight.setBrush(QBrush(self.locate_color))  # Solid fill

        self._scene.addItem(pixel_highlight)
        self.locate_items.append(pixel_highlight)

    def _show_locate_box(self):
        """Show a 1-pixel box around the target."""
        # Create a small rectangle around the target pixel
        box = QGraphicsRectItem(self.target_x - 1, self.target_y - 1, 3, 3)

        pen = QPen(self.locate_color)
        pen.setWidth(1)
        pen.setCosmetic(True)
        box.setPen(pen)
        box.setBrush(QBrush())  # No fill, just outline

        self._scene.addItem(box)
        self.locate_items.append(box)

    def _clear_locate(self):
        """Clear all locate items."""
        for item in self.locate_items:
            self._scene.removeItem(item)
        self.locate_items.clear()


# --- Main Tracker Widget ---
class TrackerWidget(QWidget):
    """Simple tracker widget."""

    def __init__(self, target_process="WidgetInc.exe"):
        super().__init__()
        self.target_process = target_process
        self.logger = logging.getLogger(self.__class__.__name__)

        # State
        self.target_found = False
        self.target_hwnd = None
        self.coordinates = {}
        self.window_xy = {}
        self.frame_xy = {}
        self.frozen = False  # Add freeze state

        # Mouse tracker
        self.mouse_tracker = MouseTracker()
        self.mouse_tracker.set_coordinate_callbacks(self._get_window_coords, self._get_frame_coords)
        self.mouse_tracker.position_changed.connect(self._on_mouse_position_changed)

        self._setup_window()
        self._setup_ui()
        self._start_monitoring()

        # Start mouse tracking
        self.mouse_tracker.start_tracking(100)  # Update every 100ms

        self.logger.info("Tracker widget initialized")

    def _setup_window(self):
        """Setup window properties."""
        self.setWindowTitle("Widget Automation Tracker")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMinimumSize(325, 100)
        self.setMaximumSize(325, 16777215)  # Disable horizontal resizing, allow vertical
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # Allow keyboard focus

        # Dark mode styling
        self.setStyleSheet(
            """
            QWidget {
                background-color: #2d2d2d;
                color: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel {
                background-color: transparent;
            }
        """
        )

        # Position in center of screen
        screen = QApplication.primaryScreen()
        if screen is not None:
            rect = screen.availableGeometry() if hasattr(screen, "availableGeometry") else screen.geometry()
            self.move((rect.width() - self.width()) // 2, (rect.height() - self.height()) // 2)
        else:
            self.move(50, 50)

    def _setup_ui(self):
        """Setup user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Title
        self.title_label = QLabel("Widget Tracker")  # <-- Make this an instance attribute
        self.title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet(
            """
            QLabel {
                color: #ffffff;
                padding: 8px;
                background-color: #3d3d3d;
                border-radius: 4px;
                margin-bottom: 4px;
            }
        """
        )

        # Hotkey hint
        hotkey_label = QLabel("Ctrl+F to freeze coordinates")
        hotkey_label.setFont(QFont("Arial", 8))
        hotkey_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hotkey_label.setStyleSheet(
            """
            QLabel {
                color: #888888;
                padding: 2px;
                background-color: transparent;
                font-style: italic;
            }
        """
        )

        # Status section
        status_layout = QHBoxLayout()

        self.status_label = QLabel("SEARCHING...")
        self.status_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.status_label.setStyleSheet(
            """
            QLabel {
                color: #cccccc;
                padding: 4px;
                background-color: transparent;
            }
        """
        )

        # Status circle
        self.status_circle = QLabel()
        self.status_circle.setFixedSize(20, 20)
        self.status_circle.setStyleSheet(
            """
            QLabel {
                background-color: #FF8C00;
                border-radius: 10px;
                border: 2px solid #FFA500;
            }
        """
        )

        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.status_circle)

        # Coordinates table
        self.coords_table = QTableWidget(2, 2)
        self.coords_table.setHorizontalHeaderLabels(["Top-Left", "Dimensions"])
        self.coords_table.setVerticalHeaderLabels(["Window", "Frame"])

        # Set table properties
        self.coords_table.setFixedHeight(90)
        self.coords_table.setAlternatingRowColors(True)
        # Fix type issues with header resize modes
        h_header = self.coords_table.horizontalHeader()
        if h_header:
            h_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        v_header = self.coords_table.verticalHeader()
        if v_header:
            v_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.coords_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)  # Disable selection

        # Style the coordinates table
        self.coords_table.setStyleSheet(
            """
            QTableWidget {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 4px;
                gridline-color: #555;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
            }
            QTableWidget::item {
                padding: 4px;
                border: none;
            }
            QHeaderView::section {
                background-color: #3d3d3d;
                color: #ffffff;
                border: 1px solid #555;
                padding: 4px;
                font-weight: bold;
            }
        """
        )

        # Initialize coordinates table with default values
        self._init_coords_table()

        # Control buttons
        button_layout = QHBoxLayout()

        self.screenshot_button = QPushButton("SCREENSHOT")
        self.screenshot_button.clicked.connect(self._take_screenshot)
        self.screenshot_button.setStyleSheet(
            """
            QPushButton {
                background-color: #388e3c;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4caf50;
            }
            QPushButton:pressed {
                background-color: #2e7d32;
            }
        """
        )

        self.restart_button = QPushButton("RESTART")
        self.restart_button.clicked.connect(self._restart_application)
        self.restart_button.setStyleSheet(
            """
            QPushButton {
                background-color: #1976d2;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2196f3;
            }
            QPushButton:pressed {
                background-color: #0d47a1;
            }
        """
        )

        self.close_button = QPushButton("CLOSE")
        self.close_button.clicked.connect(self.close)
        self.close_button.setStyleSheet(
            """
            QPushButton {
                background-color: #d32f2f;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f44336;
            }
            QPushButton:pressed {
                background-color: #b71c1c;
            }
        """
        )

        button_layout.addWidget(self.screenshot_button)
        button_layout.addStretch()
        button_layout.addWidget(self.restart_button)
        button_layout.addWidget(self.close_button)

        # Mouse tracking table
        self.mouse_table = QTableWidget(4, 2)
        self.mouse_table.setHorizontalHeaderLabels(["Actuals", "Percents"])
        self.mouse_table.setVerticalHeaderLabels(["Screen", "Window", "Frame", "Color"])

        # Set table properties
        self.mouse_table.setFixedHeight(140)
        self.mouse_table.setAlternatingRowColors(True)
        # Fix type issues with header resize modes
        h_header = self.mouse_table.horizontalHeader()
        if h_header:
            h_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        v_header = self.mouse_table.verticalHeader()
        if v_header:
            v_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.mouse_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )  # Enable single cell selection for copying
        self.mouse_table.cellClicked.connect(self.on_cell_clicked)  # Connect click handler

        # Style the table
        self.mouse_table.setStyleSheet(
            """
            QTableWidget {
                background-color: #1e1e1e;
                color: #00ff88;
                border: 1px solid #555;
                border-radius: 4px;
                gridline-color: #555;
                font-family: 'Fira Code', 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
            }
            QTableWidget::item {
                padding: 4px;
                border: none;
            }
            QTableWidget::item:selected {
                background-color: #1e1e1e;
                color: #ff0000;
            }
            QHeaderView::section {
                background-color: #3d3d3d;
                color: #ffffff;
                border: 1px solid #555;
                padding: 4px;
                font-weight: bold;
            }
        """
        )

        # Initialize table with default values
        self._init_mouse_table()

        # Add all widgets to layout
        layout.addWidget(self.title_label)
        layout.addWidget(hotkey_label)
        layout.addLayout(status_layout)
        layout.addWidget(self.coords_table)
        layout.addWidget(self.mouse_table)
        layout.addLayout(button_layout)

        # Standard context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)

        # Add close action
        close_action = QAction("Close", self)
        close_action.triggered.connect(self.close)
        self.addAction(close_action)

    def _init_coords_table(self):
        """Initialize the coordinates table with default values."""
        # Screen row
        self.coords_table.setItem(0, 0, QTableWidgetItem("N/A"))
        self.coords_table.setItem(0, 1, QTableWidgetItem("N/A"))

        # Window row
        self.coords_table.setItem(1, 0, QTableWidgetItem("N/A"))
        self.coords_table.setItem(1, 1, QTableWidgetItem("N/A"))

        # Frame row
        self.coords_table.setItem(2, 0, QTableWidgetItem("N/A"))
        self.coords_table.setItem(2, 1, QTableWidgetItem("N/A"))

    def _init_mouse_table(self):
        """Initialize the mouse tracking table with default values."""
        # Screen row
        self.mouse_table.setItem(0, 0, QTableWidgetItem("0, 0"))
        self.mouse_table.setItem(0, 1, QTableWidgetItem("N/A"))

        # Window row
        self.mouse_table.setItem(1, 0, QTableWidgetItem("Outside"))
        self.mouse_table.setItem(1, 1, QTableWidgetItem("N/A"))

        # Frame row
        self.mouse_table.setItem(2, 0, QTableWidgetItem("Outside"))
        self.mouse_table.setItem(2, 1, QTableWidgetItem("N/A"))

        # Color row
        self.mouse_table.setItem(3, 0, QTableWidgetItem("#000000"))
        self.mouse_table.setItem(3, 1, QTableWidgetItem("0, 0, 0"))

    def on_cell_clicked(self, row: int, column: int) -> None:
        """Handle cell clicks to copy values to clipboard."""
        item = self.mouse_table.item(row, column)
        if item is None:
            return

        text = item.text()
        if text == "N/A" or text == "Outside":
            return

        copied_text = ""
        # For percentage values, extract and format with 6 decimal precision
        if column == 1 and "%" in text:  # Percents column
            # Extract percentages from text like "25.50%, 75.20%"
            percentages = []
            parts = text.replace("%", "").split(", ")
            for part in parts:
                try:
                    value = float(part)
                    percentages.append(f"{value / 100:.6f}")  # Convert to decimal with 6 precision
                except ValueError:
                    continue
            if percentages:
                copied_text = ", ".join(percentages)
                pyperclip.copy(copied_text)
        else:
            # Copy actual values as-is
            copied_text = text
            pyperclip.copy(text)

        # Show visual feedback that something was copied
        if copied_text:
            self.logger.info(f"Copied to clipboard: {copied_text}")
            self._show_copy_feedback(copied_text)

    def _take_screenshot(self):
        """Take a screenshot of the frame area and open viewer."""
        if not self.frame_xy:
            self.logger.warning("No frame area available for screenshot")
            return

        try:
            # Get frame coordinates
            frame_x = self.frame_xy.get("x", 0)
            frame_y = self.frame_xy.get("y", 0)
            frame_width = self.frame_xy.get("width", 0)
            frame_height = self.frame_xy.get("height", 0)

            if frame_width <= 0 or frame_height <= 0:
                self.logger.warning("Invalid frame dimensions for screenshot")
                return

            # Take screenshot of frame area
            bbox = (frame_x, frame_y, frame_x + frame_width, frame_y + frame_height)
            screenshot = ImageGrab.grab(bbox=bbox, all_screens=True)

            # Open screenshot viewer
            viewer = ScreenshotViewer(self.frame_xy.copy(), screenshot)
            viewer.show()

            # Keep reference to prevent garbage collection
            if not hasattr(self, "_screenshot_viewers"):
                self._screenshot_viewers = []
            self._screenshot_viewers.append(viewer)

            self.logger.info(f"Screenshot taken: {frame_width}x{frame_height} at ({frame_x}, {frame_y})")

        except Exception as e:
            self.logger.error(f"Failed to take screenshot: {e}")

    def _start_monitoring(self):
        """Start monitoring for target process."""
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._check_target)
        self.monitor_timer.start(2000)  # Check every 2 seconds

        # Initial check
        self._check_target()

    def _check_target(self):
        """Check for target process using shared utilities."""
        target_info = find_target_window(self.target_process)

        if target_info:
            # Target found - extract information
            pid = target_info["pid"]
            window_info = target_info["window_info"]
            frame_area = target_info["frame_area"]

            # Create info dict compatible with existing update logic
            found_info = {
                "pid": pid,
                "hwnd": window_info["hwnd"],
                "title": window_info["title"],
                "rect": window_info["window_rect"],
                "client_rect": (
                    0,
                    0,
                    window_info["client_width"],
                    window_info["client_height"],
                ),
                "window_info": window_info,
                "frame_area": frame_area,
                "refinement_applied": target_info.get("refinement_applied", False),
            }

            self._update_status(True, found_info)
        else:
            # Target not found
            self._update_status(False, {})

    def _update_status(self, found: bool, target_info: dict):
        """Update status display."""
        if found:
            # Update status with process name and PID
            pid = target_info.get("pid", "unknown")
            self.status_label.setText(f"{self.target_process} (PID: {pid})")
            self.status_circle.setStyleSheet(
                """
                QLabel {
                    background-color: #4CAF50;
                    border-radius: 10px;
                    border: 2px solid #66BB6A;
                }
            """
            )

            # Always update coordinates when found
            if "rect" in target_info and "client_rect" in target_info:
                rect = target_info["rect"]

                # Update Window row
                window_width = rect[2] - rect[0]
                window_height = rect[3] - rect[1]
                self.coords_table.setItem(0, 0, QTableWidgetItem(f"{rect[0]}, {rect[1]}"))
                self.coords_table.setItem(0, 1, QTableWidgetItem(f"{window_width}x{window_height}"))

                # Update Frame row
                if "frame_area" in target_info and target_info["frame_area"]:
                    frame = target_info["frame_area"]
                    self.coords_table.setItem(1, 0, QTableWidgetItem(f"{frame['x']}, {frame['y']}"))
                    self.coords_table.setItem(1, 1, QTableWidgetItem(f"{frame['width']}x{frame['height']}"))

                    # Always update tracker coordinates
                    self.window_xy = target_info["window_info"]
                    self.frame_xy = frame
                else:
                    self.coords_table.setItem(1, 0, QTableWidgetItem("N/A"))
                    self.coords_table.setItem(1, 1, QTableWidgetItem("N/A"))

        elif self.target_found:
            # Only update UI when going from found to not found
            self.status_label.setText("SEARCHING...")
            self.status_circle.setStyleSheet(
                """
                QLabel {
                    background-color: #FFA500;
                    border-radius: 10px;
                    border: 2px solid #FF8C00;
                }
            """
            )
            # Reset coordinates table to N/A
            for row in range(2):
                self.coords_table.setItem(row, 0, QTableWidgetItem("N/A"))
                self.coords_table.setItem(row, 1, QTableWidgetItem("N/A"))
            self.window_xy = {}
            self.frame_xy = {}

        # Update status flag
        self.target_found = found

    def _get_window_coords(self) -> Dict:
        """Callback to provide window coordinates to mouse tracker."""
        return self.window_xy

    def _get_frame_coords(self) -> Dict:
        """Callback to provide frame coordinates to mouse tracker."""
        return self.frame_xy

    def _on_mouse_position_changed(self, position_info: Dict):
        """Handle mouse position updates from mouse tracker."""
        # Skip updates if frozen
        if self.frozen:
            return

        try:
            screen_x = position_info.get("screen_x", 0)
            screen_y = position_info.get("screen_y", 0)

            # Get color at current mouse position
            try:
                color = pyautogui.pixel(screen_x, screen_y)
                hex_color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
                rgb_color = f"{color[0]}, {color[1]}, {color[2]}"
            except Exception:
                hex_color = "#000000"
                rgb_color = "0, 0, 0"

            # Update Screen row
            self.mouse_table.setItem(0, 0, QTableWidgetItem(f"{screen_x}, {screen_y}"))
            self.mouse_table.setItem(0, 1, QTableWidgetItem("N/A"))

            # Update Window row
            if position_info.get("inside_window", False):
                window_x_percent = position_info.get("window_x_percent", 0)
                window_y_percent = position_info.get("window_y_percent", 0)
                self.mouse_table.setItem(1, 0, QTableWidgetItem(f"{screen_x}, {screen_y}"))
                self.mouse_table.setItem(1, 1, QTableWidgetItem(f"{window_x_percent:.2f}%, {window_y_percent:.2f}%"))
            else:
                self.mouse_table.setItem(1, 0, QTableWidgetItem("Outside"))
                self.mouse_table.setItem(1, 1, QTableWidgetItem("N/A"))

            # Update Frame row
            if position_info.get("inside_window", False):
                # Inside window - check if also inside frame
                if position_info.get("inside_frame", False):
                    frame_x = position_info.get("frame_x", 0)
                    frame_y = position_info.get("frame_y", 0)
                    x_percent = position_info.get("x_percent", 0)
                    y_percent = position_info.get("y_percent", 0)
                    self.mouse_table.setItem(2, 0, QTableWidgetItem(f"{frame_x}, {frame_y}"))
                    self.mouse_table.setItem(2, 1, QTableWidgetItem(f"{x_percent:.2f}%, {y_percent:.2f}%"))
                else:
                    # Inside window but outside frame - show clamped coordinates with frame percentages
                    if self.frame_xy:
                        # Calculate frame-relative coordinates even when outside frame bounds
                        frame_x_raw = screen_x - self.frame_xy.get("x", 0)
                        frame_y_raw = screen_y - self.frame_xy.get("y", 0)
                        frame_width = self.frame_xy.get("width", 1)
                        frame_height = self.frame_xy.get("height", 1)

                        # Clamp coordinates to frame bounds
                        frame_x = max(0, min(frame_x_raw, frame_width))
                        frame_y = max(0, min(frame_y_raw, frame_height))

                        # Clamp percentages to 0-100%
                        x_percent = max(0.0, min(100.0, 100 * frame_x_raw / max(1, frame_width)))
                        y_percent = max(0.0, min(100.0, 100 * frame_y_raw / max(1, frame_height)))

                        self.mouse_table.setItem(2, 0, QTableWidgetItem(f"{frame_x}, {frame_y}"))
                        self.mouse_table.setItem(2, 1, QTableWidgetItem(f"{x_percent:.2f}%, {y_percent:.2f}%"))
                    else:
                        self.mouse_table.setItem(2, 0, QTableWidgetItem("N/A"))
                        self.mouse_table.setItem(2, 1, QTableWidgetItem("N/A"))
            else:
                # Outside window - show "Outside" for frame
                self.mouse_table.setItem(2, 0, QTableWidgetItem("Outside"))
                self.mouse_table.setItem(2, 1, QTableWidgetItem("N/A"))

            # Update Color row
            self.mouse_table.setItem(3, 0, QTableWidgetItem(hex_color))
            self.mouse_table.setItem(3, 1, QTableWidgetItem(rgb_color))

        except Exception as e:
            self.logger.error(f"Error updating mouse display: {e}")
            # Reset table to error state
            for row in range(4):  # Updated to 4 rows
                self.mouse_table.setItem(row, 0, QTableWidgetItem("Error"))
                self.mouse_table.setItem(row, 1, QTableWidgetItem("Error"))

    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key.Key_F and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            # Toggle freeze state (Ctrl+F)
            self.frozen = not self.frozen
            freeze_status = "FROZEN" if self.frozen else "TRACKING"

            # Update freeze status display
            freeze_item = QTableWidgetItem(freeze_status)
            if self.frozen:
                freeze_item.setBackground(Qt.GlobalColor.darkRed)
            else:
                freeze_item.setBackground(Qt.GlobalColor.darkGreen)

            # This will be shown in the Color row for now since we removed the separate freeze row
            # We'll update the status through visual styling instead

            self.logger.info(f"Coordinate tracking {'frozen' if self.frozen else 'resumed'}")

            # Visual feedback in title
            original_title = self.windowTitle()
            self.setWindowTitle(f"Widget Tracker - {freeze_status}")
            QTimer.singleShot(1500, lambda: self.setWindowTitle(original_title))
        else:
            super().keyPressEvent(event)

    def _show_copy_feedback(self, copied_text: str):
        """Show visual feedback that text was copied to clipboard."""
        # Flash the title label green with copied text
        original_title = self.windowTitle()
        original_text = self.title_label.text()

        # Update title and label to show what was copied
        self.setWindowTitle(f"Widget Tracker - Copied: {copied_text}")
        self.title_label.setText(f"Copied: {copied_text}")

        # Call the existing green flash method
        self._show_title_copied_feedback()

        # Restore original text and title after 2 seconds
        QTimer.singleShot(2000, lambda: self.setWindowTitle(original_title))
        QTimer.singleShot(2000, lambda: self.title_label.setText(original_text))

    def _show_title_copied_feedback(self):
        """Flash the title label green and fade back to normal."""
        # Set green background
        self.title_label.setStyleSheet(
            """
            QLabel {
                color: #ffffff;
                padding: 8px;
                background-color: #2ecc40;
                border-radius: 4px;
                margin-bottom: 4px;
            }
            """
        )
        # Fade back to normal after 2 seconds to match the text duration
        QTimer.singleShot(2000, self._reset_title_label_style)

    def _reset_title_label_style(self):
        """Restore the title label's normal background."""
        self.title_label.setStyleSheet(
            """
            QLabel {
                color: #ffffff;
                padding: 8px;
                background-color: #3d3d3d;
                border-radius: 4px;
                margin-bottom: 4px;
            }
            """
        )

    def _restart_application(self):
        """Restart the tracker application."""
        try:
            self.logger.info("Restarting tracker application...")

            # Get the current executable path
            if getattr(sys, "frozen", False):
                # Running as compiled exe
                executable = sys.executable
                args = [executable] + sys.argv[1:]  # Include command line arguments
            else:
                # Running as Python script
                executable = sys.executable
                args = [executable, __file__] + sys.argv[1:]  # Include script file and arguments

            # Close current application
            self.close()

            # Start new instance
            subprocess.Popen(args, cwd=os.getcwd())

            # Exit current process
            QApplication.quit()

        except Exception as e:
            self.logger.error(f"Failed to restart application: {e}")

    def closeEvent(self, event):
        """Clean up when closing the tracker."""
        super().closeEvent(event)


# --- Logging and CLI ---
def setup_logging():
    """Setup basic logging for tracker."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    return logging.getLogger(__name__)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Widget Automation Tracker")

    parser.add_argument(
        "--target",
        default="WidgetInc.exe",
        help="Target process name to track (default: WidgetInc.exe)",
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_arguments()
    logger = setup_logging()

    logger.info(f"Starting tracker for {args.target}")

    app = QApplication(sys.argv)

    tracker = TrackerWidget(args.target)
    tracker.show()

    # Signal handling
    def signal_handler(signum, frame):
        logger.info("Shutdown signal received")
        tracker.close()
        app.quit()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
