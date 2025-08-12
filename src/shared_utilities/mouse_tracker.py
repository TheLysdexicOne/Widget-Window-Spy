"""MouseTracker extraction.

Preserves behaviour; only import paths updated.
"""

from __future__ import annotations
from typing import Callable, Dict, Optional
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
import ctypes
from .coordinates import CoordinateSystem


class MouseTracker(QObject):
    position_changed = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self._window_xy_cb: Optional[Callable[[], Dict]] = None
        self._frame_xy_cb: Optional[Callable[[], Dict]] = None
        self._timer: Optional[QTimer] = None
        self.coord_system = CoordinateSystem()
        self.last_position_info = {}

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
        self.last_position_info = pos_info
        self.position_changed.emit(pos_info)

    def _get_position_info(self) -> Dict:
        try:

            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

            pt = POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            screen_x, screen_y = pt.x, pt.y
        except Exception:
            screen_x, screen_y = 0, 0
        info = {"screen_x": screen_x, "screen_y": screen_y}
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
        if self._frame_xy_cb:
            frame = self._frame_xy_cb()
            if frame:
                self.coord_system.update_frame_area(frame)
                if self.coord_system.is_inside_frame(screen_x, screen_y):
                    info["inside_frame"] = True
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
