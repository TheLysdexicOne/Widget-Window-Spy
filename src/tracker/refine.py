"""Frame border refinement utilities (PyAutoGUI based).

Split from monolithic tracker file. Logic preserved verbatim.
"""

from __future__ import annotations
from typing import Dict, Optional

import pyautogui  # type: ignore


def _refine_frame_borders_pyautogui(frame_area: Dict) -> Optional[Dict]:
    if not frame_area:
        return None
    x = frame_area.get("x", 0)
    y = frame_area.get("y", 0)
    width = frame_area.get("width", 0)
    height = frame_area.get("height", 0)
    target_width = 2054
    if abs(width - target_width) > 10:
        return None
    try:
        validation_y = y + height // 2
        width_diff = target_width - width
        if width_diff == 0:
            return frame_area
        if width == 2053 and target_width == 2054:
            return {"x": x, "y": y, "width": target_width, "height": height}
        adjustments = []
        if abs(width_diff) <= 4:
            if width_diff > 0:
                adjustments = [
                    (0, width_diff),
                    (-width_diff, 0),
                    (-width_diff // 2, width_diff // 2 + width_diff % 2),
                ]
            else:
                width_diff = abs(width_diff)
                adjustments = [
                    (0, -width_diff),
                    (width_diff, 0),
                    (width_diff // 2, -(width_diff // 2 + width_diff % 2)),
                ]
        for left_adj, right_adj in adjustments:
            new_x = x + left_adj
            new_width = width - left_adj + right_adj
            if new_width == target_width:
                left_x = new_x - 1
                right_x = new_x + new_width
                if left_x >= -3840 and right_x < 7680:
                    try:
                        left_pixel = pyautogui.pixel(left_x, validation_y)
                        right_pixel = pyautogui.pixel(right_x, validation_y)
                        if left_pixel != right_pixel:
                            return {"x": new_x, "y": y, "width": new_width, "height": height}
                    except Exception:
                        continue
        return frame_area
    except Exception:
        return frame_area
