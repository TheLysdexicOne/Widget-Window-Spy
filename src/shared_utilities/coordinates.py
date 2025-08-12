"""Coordinate system management classes.

Minimal extraction from original monolithic file.
"""

from __future__ import annotations
from typing import Dict


class CoordinateSystem:
    def __init__(self):
        self.frame_area = None

    def update_frame_area(self, frame_area: Dict):
        self.frame_area = frame_area

    def is_inside_frame(self, screen_x: int, screen_y: int) -> bool:
        if not self.frame_area:
            return False
        px = self.frame_area.get("x", 0)
        py = self.frame_area.get("y", 0)
        pw = self.frame_area.get("width", 0)
        ph = self.frame_area.get("height", 0)
        return px <= screen_x <= px + pw and py <= screen_y <= py + ph
