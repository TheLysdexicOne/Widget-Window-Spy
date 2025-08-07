#!/usr/bin/env python3
"""
Coordinate system management for Widget Window Spy.
Handles conversion between screen, frame, and percentage coordinates.
"""

from typing import Dict, Tuple, Optional
from core.constants import TARGET_ASPECT_RATIO


class CoordinateSystem:
    """
    Centralized coordinate system manager.
    Handles conversion between screen, frame, and percentage coordinates.
    """

    def __init__(self):
        self.frame_area: Optional[Dict] = None

    def update_frame_area(self, frame_area: Dict) -> None:
        """Update the current frame area."""
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

    def screen_to_frame_coords(self, screen_x: int, screen_y: int) -> Tuple[int, int]:
        """Convert screen coordinates to frame-relative coordinates."""
        if not self.frame_area:
            return screen_x, screen_y

        frame_x = screen_x - self.frame_area.get("x", 0)
        frame_y = screen_y - self.frame_area.get("y", 0)
        return frame_x, frame_y

    def frame_to_screen_coords(self, frame_x: int, frame_y: int) -> Tuple[int, int]:
        """Convert frame-relative coordinates to screen coordinates."""
        if not self.frame_area:
            return frame_x, frame_y

        screen_x = frame_x + self.frame_area.get("x", 0)
        screen_y = frame_y + self.frame_area.get("y", 0)
        return screen_x, screen_y

    def frame_to_percentage(self, frame_x: int, frame_y: int) -> Tuple[float, float]:
        """Convert frame coordinates to percentage (0-100)."""
        if not self.frame_area:
            return 0.0, 0.0

        width = self.frame_area.get("width", 1)
        height = self.frame_area.get("height", 1)

        x_percent = 100.0 * frame_x / max(1, width)
        y_percent = 100.0 * frame_y / max(1, height)
        return x_percent, y_percent

    def percentage_to_frame(self, x_percent: float, y_percent: float) -> Tuple[int, int]:
        """Convert percentage (0-100) to frame coordinates."""
        if not self.frame_area:
            return 0, 0

        width = self.frame_area.get("width", 1)
        height = self.frame_area.get("height", 1)

        frame_x = int(x_percent * width / 100.0)
        frame_y = int(y_percent * height / 100.0)
        return frame_x, frame_y

    def auto_detect_coordinate_type(self, x: float, y: float) -> str:
        """
        Auto-detect coordinate type based on values.
        Returns: 'decimal_percent', 'integer_percent', 'screen', or 'frame'
        """
        if 0 <= x <= 1.0 and 0 <= y <= 1.0:
            return "decimal_percent"
        elif 0 <= x <= 100 and 0 <= y <= 100 and (x > 1.0 or y > 1.0):
            return "integer_percent"
        elif x >= 1000 or y >= 1000:
            return "screen"
        else:
            return "frame"

    def convert_to_frame_coords(self, x: float, y: float) -> Tuple[float, float]:
        """Convert any coordinate type to frame coordinates."""
        coord_type = self.auto_detect_coordinate_type(x, y)

        if coord_type == "decimal_percent":
            # 0.0-1.0 decimal percentages
            return self.percentage_to_frame(x * 100, y * 100)
        elif coord_type == "integer_percent":
            # 0-100 integer percentages
            return self.percentage_to_frame(x, y)
        elif coord_type == "screen":
            # Screen coordinates
            return self.screen_to_frame_coords(int(x), int(y))
        else:
            # Already frame coordinates
            return x, y

    def calculate_frame_area(self, client_x: int, client_y: int, client_w: int, client_h: int) -> Dict:
        """
        Calculate 3:2 aspect ratio frame area within client area.
        Returns frame area dictionary with x, y, width, height.
        """
        client_ratio = client_w / client_h if client_h else 1

        if client_ratio > TARGET_ASPECT_RATIO:
            # Client is wider than 3:2 - fit height, center width
            frame_height = client_h
            frame_width = int(frame_height * TARGET_ASPECT_RATIO)
            px = client_x + (client_w - frame_width) // 2
            py = client_y
        else:
            # Client is taller than 3:2 - fit width, center height
            frame_width = client_w
            frame_height = int(frame_width / TARGET_ASPECT_RATIO)
            px = client_x
            py = client_y + (client_h - frame_height) // 2

        return {"x": px, "y": py, "width": frame_width, "height": frame_height}

    def get_frame_info(self) -> Dict:
        """Get current frame area information."""
        return self.frame_area.copy() if self.frame_area else {}

    def clamp_to_frame_bounds(self, frame_x: int, frame_y: int) -> Tuple[int, int]:
        """Clamp coordinates to frame boundaries."""
        if not self.frame_area:
            return frame_x, frame_y

        width = self.frame_area.get("width", 1)
        height = self.frame_area.get("height", 1)

        clamped_x = max(0, min(frame_x, width))
        clamped_y = max(0, min(frame_y, height))
        return clamped_x, clamped_y

    def clamp_percentage_bounds(self, x_percent: float, y_percent: float) -> Tuple[float, float]:
        """Clamp percentage values to 0-100 range."""
        clamped_x = max(0.0, min(100.0, x_percent))
        clamped_y = max(0.0, min(100.0, y_percent))
        return clamped_x, clamped_y
