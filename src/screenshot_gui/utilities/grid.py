from __future__ import annotations
from PyQt6.QtGui import QPen, QColor
from PyQt6.QtWidgets import QGraphicsItemGroup, QGraphicsLineItem


def base_steps(frame_area: dict) -> tuple[float, float]:
    """Legacy compatibility - returns (1.0, 1.0) for pixel-perfect grid."""
    return 1.0, 1.0


def create_pixel_grid(width: int, height: int, frame_area: dict, scale_factor: float) -> QGraphicsItemGroup | None:
    """Create a pixel-perfect grid based on zoom level.

    Grid spacing:
    1x = 16px, 2x = 8px, 4x = 4px, 8x = 2px, 16x = 1px
    """
    if scale_factor <= 0:
        return None

    group = QGraphicsItemGroup()
    pen = QPen(QColor(0, 255, 255, 128))
    pen.setWidth(1)
    pen.setCosmetic(True)

    # Determine grid spacing based on zoom level
    if scale_factor >= 16:
        grid_spacing = 1
    elif scale_factor >= 8:
        grid_spacing = 2
    elif scale_factor >= 4:
        grid_spacing = 4
    elif scale_factor >= 2:
        grid_spacing = 8
    else:  # 1x zoom
        grid_spacing = 16

    # Draw vertical lines (columns)
    x = 0
    while x <= width:
        line = QGraphicsLineItem(x, 0, x, height)
        line.setPen(pen)
        group.addToGroup(line)
        x += grid_spacing

    # Draw horizontal lines (rows)
    y = 0
    while y <= height:
        line = QGraphicsLineItem(0, y, width, y)
        line.setPen(pen)
        group.addToGroup(line)
        y += grid_spacing

    return group
