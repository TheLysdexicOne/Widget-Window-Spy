from __future__ import annotations
import pyperclip


class CopyModeManager:
    MODES = ["PERCENTAGE", "FRAME COORDS", "SCREEN COORDS"]

    def __init__(self):
        self.index = 0

    @property
    def mode(self) -> str:
        return self.MODES[self.index]

    def cycle(self) -> str:
        self.index = (self.index + 1) % len(self.MODES)
        return self.mode

    def copy_point(self, frame_x: float, frame_y: float, frame_area: dict):
        if self.mode == "PERCENTAGE":
            fw = max(1, frame_area.get("width", 1))
            fh = max(1, frame_area.get("height", 1))
            pyperclip.copy(f"{frame_x / fw:.6f}, {frame_y / fh:.6f}")
        elif self.mode == "FRAME COORDS":
            pyperclip.copy(f"{int(frame_x)}, {int(frame_y)}")
        else:
            fx = frame_area.get("x", 0)
            fy = frame_area.get("y", 0)
            pyperclip.copy(f"{fx + int(frame_x)}, {fy + int(frame_y)}")

    def copy_rect(self, rect, frame_area: dict):
        x1, y1, x2, y2 = rect
        if self.mode == "PERCENTAGE":
            fw = max(1, frame_area.get("width", 1))
            fh = max(1, frame_area.get("height", 1))
            pyperclip.copy(f"{x1 / fw:.6f}, {y1 / fh:.6f}, {x2 / fw:.6f}, {y2 / fh:.6f}")
        elif self.mode == "FRAME COORDS":
            pyperclip.copy(f"{int(x1)}, {int(y1)}, {int(x2)}, {int(y2)}")
        else:
            fx = frame_area.get("x", 0)
            fy = frame_area.get("y", 0)
            pyperclip.copy(f"{fx + int(x1)}, {fy + int(y1)}, {fx + int(x2)}, {fy + int(y2)}")
