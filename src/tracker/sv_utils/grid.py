from __future__ import annotations
from PyQt6.QtGui import QPen, QColor
from PyQt6.QtWidgets import QGraphicsItemGroup, QGraphicsLineItem

BASE_W = 1080
BASE_H = 720
PIXEL_ART_GRID_WIDTH = 192
PIXEL_ART_GRID_HEIGHT = 128


def base_steps(frame_area: dict) -> tuple[float, float]:
    fw = float(max(1, frame_area.get("width", 1)))
    fh = float(max(1, frame_area.get("height", 1)))
    return fw / PIXEL_ART_GRID_WIDTH, fh / PIXEL_ART_GRID_HEIGHT


def create_pixel_grid(width: int, height: int, frame_area: dict, scale_factor: float) -> QGraphicsItemGroup | None:
    step_x, step_y = base_steps(frame_area)
    if step_x <= 0 or step_y <= 0:
        return None

    group = QGraphicsItemGroup()
    pen = QPen(QColor(0, 255, 255, 128))
    pen.setWidth(1)
    pen.setCosmetic(True)
    scale_factor = max(0.0001, scale_factor)
    px_x = step_x * scale_factor
    px_y = step_y * scale_factor

    def stride(px: float) -> int:
        if px >= 8:
            return 1
        if px >= 4:
            return 2
        if px >= 2:
            return 5
        return 10

    col_stride = stride(px_x)
    row_stride = stride(px_y)

    # Draw vertical lines (columns) - aligned to logical grid
    for i in range(0, PIXEL_ART_GRID_WIDTH + 1, col_stride):
        x = i * step_x
        if 0 <= x <= width:  # Only draw lines that are visible in the frame
            line = QGraphicsLineItem(x, 0, x, height)
            line.setPen(pen)
            group.addToGroup(line)

    # Draw horizontal lines (rows) - aligned to logical grid
    for j in range(0, PIXEL_ART_GRID_HEIGHT + 1, row_stride):
        y = j * step_y
        if 0 <= y <= height:  # Only draw lines that are visible in the frame
            line = QGraphicsLineItem(0, y, width, y)
            line.setPen(pen)
            group.addToGroup(line)

    return group
