#!/usr/bin/env python3
"""
Mouse tracking system for Widget Window Spy.
Provides real-time mouse position monitoring with coordinate system conversion.
"""

import ctypes
from typing import Callable, Dict, Optional
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from core.coordinates import CoordinateSystem
from core.constants import TIMER_MOUSE_TRACKING_INTERVAL


class MouseTracker(QObject):
    """
    Global mouse position monitoring with coordinate system conversion.
    Emits position_changed signal with comprehensive coordinate information.
    """

    position_changed = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self._window_xy_cb: Optional[Callable[[], Dict]] = None
        self._frame_xy_cb: Optional[Callable[[], Dict]] = None
        self._timer: Optional[QTimer] = None
        self.coord_system = CoordinateSystem()
        self.last_position_info = {}

    def set_coordinate_callbacks(self, window_cb: Callable[[], Dict], frame_cb: Callable[[], Dict]) -> None:
        """Set callbacks to get current window and frame information."""
        self._window_xy_cb = window_cb
        self._frame_xy_cb = frame_cb

    def start_tracking(self, interval_ms: int = TIMER_MOUSE_TRACKING_INTERVAL) -> None:
        """Start mouse position tracking with specified interval."""
        if self._timer is None:
            self._timer = QTimer()
            self._timer.timeout.connect(self._emit_position)
            self._timer.start(interval_ms)

    def stop_tracking(self) -> None:
        """Stop mouse position tracking."""
        if self._timer:
            self._timer.stop()
            self._timer = None

    def _emit_position(self) -> None:
        """Emit current mouse position information."""
        pos_info = self._get_position_info()
        self.last_position_info = pos_info
        self.position_changed.emit(pos_info)

    def _get_position_info(self) -> Dict:
        """Get comprehensive mouse position information across all coordinate systems."""
        # Get raw mouse position using Windows API
        screen_x, screen_y = self._get_cursor_position()

        info = {"screen_x": screen_x, "screen_y": screen_y}

        # Add window information if callback is available
        self._add_window_info(info, screen_x, screen_y)

        # Add frame information if callback is available
        self._add_frame_info(info, screen_x, screen_y)

        return info

    def _get_cursor_position(self) -> tuple[int, int]:
        """Get current cursor position using Windows API."""
        try:

            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

            pt = POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            return pt.x, pt.y
        except Exception:
            return 0, 0

    def _add_window_info(self, info: Dict, screen_x: int, screen_y: int) -> None:
        """Add window-relative coordinate information."""
        if not self._window_xy_cb:
            return

        win_info = self._window_xy_cb()
        if not win_info or "window_rect" not in win_info:
            return

        wx1, wy1, wx2, wy2 = win_info["window_rect"]
        if wx1 <= screen_x <= wx2 and wy1 <= screen_y <= wy2:
            info["inside_window"] = True
            info["window_x_percent"] = 100 * (screen_x - wx1) / max(1, wx2 - wx1)
            info["window_y_percent"] = 100 * (screen_y - wy1) / max(1, wy2 - wy1)
        else:
            info["inside_window"] = False

    def _add_frame_info(self, info: Dict, screen_x: int, screen_y: int) -> None:
        """Add frame-relative coordinate information."""
        if not self._frame_xy_cb:
            return

        frame = self._frame_xy_cb()
        if not frame:
            return

        # Update coordinate system with current frame
        self.coord_system.update_frame_area(frame)

        # Check if mouse is inside frame area
        if self.coord_system.is_inside_frame(screen_x, screen_y):
            info["inside_frame"] = True

            # Calculate frame-relative coordinates
            frame_x, frame_y = self.coord_system.screen_to_frame_coords(screen_x, screen_y)
            info["frame_x"] = frame_x
            info["frame_y"] = frame_y

            # Calculate frame percentages
            x_percent, y_percent = self.coord_system.frame_to_percentage(frame_x, frame_y)
            info["x_percent"] = x_percent
            info["y_percent"] = y_percent
        else:
            info["inside_frame"] = False

    def get_last_position(self) -> Dict:
        """Get the last recorded mouse position information."""
        return self.last_position_info.copy()

    def is_tracking(self) -> bool:
        """Check if mouse tracking is currently active."""
        return self._timer is not None and self._timer.isActive()
