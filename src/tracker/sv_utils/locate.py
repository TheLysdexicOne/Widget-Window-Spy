from __future__ import annotations
import re
from PyQt6.QtGui import QColor, QPen
from PyQt6.QtWidgets import QGraphicsRectItem
from PIL import Image

# Parsing
POINT_RE = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*,\s*([0-9]*\.?[0-9]+)\s*$")
BBOX_RE = re.compile(
    r"^\s*([0-9]*\.?[0-9]+)\s*,\s*([0-9]*\.?[0-9]+)\s*,\s*([0-9]*\.?[0-9]+)\s*,\s*([0-9]*\.?[0-9]+)\s*$"
)


def parse_coordinates(text: str, mode: str, frame_area: dict):
    text = text.strip().replace(" ", "")
    m = BBOX_RE.match(text)
    if m:
        x1, y1, x2, y2 = map(float, m.groups())
        return {"type": "bbox", "x1": x1, "y1": y1, "x2": x2, "y2": y2}
    m = POINT_RE.match(text)
    if m:
        x, y = map(float, m.groups())
        return {"type": "point", "x": x, "y": y}
    return None


def convert_to_scene_coords(x: float, y: float, mode: str, frame_area: dict):
    if mode == "PERCENTAGE":
        fw = frame_area.get("width", 1)
        fh = frame_area.get("height", 1)
        return x * fw, y * fh
    if mode == "FRAME COORDS":
        return x, y
    if mode == "SCREEN COORDS":
        fx = frame_area.get("x", 0)
        fy = frame_area.get("y", 0)
        return x - fx, y - fy
    return x, y


def draw_bbox(scene, x1, y1, x2, y2, color: QColor = QColor(255, 255, 0)):
    left, top = min(x1, x2), min(y1, y2)
    right, bottom = max(x1, x2), max(y1, y2)
    rect = QGraphicsRectItem(left, top, right - left, bottom - top)
    pen = QPen(color)
    pen.setWidth(2)
    pen.setCosmetic(True)
    rect.setPen(pen)
    scene.addItem(rect)
    return rect


def start_locate_animation(viewer, target_x, target_y, screenshot: Image.Image):
    viewer.target_x = target_x
    viewer.target_y = target_y
    try:
        if 0 <= int(target_x) < screenshot.width and 0 <= int(target_y) < screenshot.height:
            pixel_color = screenshot.getpixel((int(target_x), int(target_y)))
            if isinstance(pixel_color, tuple) and len(pixel_color) >= 3:
                viewer.locate_color = (
                    QColor(255, 255, 0) if all(c > 200 for c in pixel_color[:3]) else QColor(255, 255, 255)
                )
            else:
                viewer.locate_color = QColor(255, 255, 255)
        else:
            viewer.locate_color = QColor(255, 255, 255)
    except Exception:
        viewer.locate_color = QColor(255, 255, 255)
    viewer.locate_timer.start(100)
