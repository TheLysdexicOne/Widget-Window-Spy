from __future__ import annotations
from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QColor, QPen, QBrush
from PyQt6.QtWidgets import QGraphicsRectItem
import pyperclip


class BBoxTool:
    def __init__(self, scene, frame_area: dict, copy_mode_manager):
        self.scene = scene
        self.frame_area = frame_area
        self.copy_mode_manager = copy_mode_manager
        self.rect_item: QGraphicsRectItem | None = None
        self.dragging = False
        self.resizing = False
        self.resize_direction = None
        self._rect_f: QRectF | None = None

    def ensure_created(self, pixmap_width: int, pixmap_height: int):
        if self.rect_item is None:
            w = max(40, pixmap_width * 0.2)
            h = max(40, pixmap_height * 0.2)
            left = (pixmap_width - w) / 2
            top = (pixmap_height - h) / 2
            self.rect_item = QGraphicsRectItem(left, top, w, h)
            pen = QPen(QColor(255, 255, 0))
            pen.setWidth(2)
            pen.setCosmetic(True)
            self.rect_item.setPen(pen)
            self.rect_item.setBrush(QBrush())
            self.scene.addItem(self.rect_item)
            self._rect_f = QRectF(left, top, w, h)
            self.update_clipboard()

    def detect_resize_direction(self, scene_pos, scale: float):
        if self.rect_item is None:
            return None
        r = self.rect_item.rect()
        corner_thr = max(6, 10 / max(0.5, scale))
        edge_margin = max(4, 8 / max(0.5, scale))
        for pt, d in [
            (r.topLeft(), "nw"),
            (r.topRight(), "ne"),
            (r.bottomLeft(), "sw"),
            (r.bottomRight(), "se"),
        ]:
            if (scene_pos - pt).manhattanLength() <= corner_thr * 2:
                return d
        x = scene_pos.x()
        y = scene_pos.y()
        if (
            r.left() - edge_margin <= x <= r.right() + edge_margin
            and r.top() - edge_margin <= y <= r.bottom() + edge_margin
        ):
            if r.top() - edge_margin <= y <= r.top() + edge_margin:
                return "n"
            if r.bottom() - edge_margin <= y <= r.bottom() + edge_margin:
                return "s"
            if r.left() - edge_margin <= x <= r.left() + edge_margin:
                return "w"
            if r.right() - edge_margin <= x <= r.right() + edge_margin:
                return "e"
        return None

    def begin_drag(self):
        if self.rect_item is None:
            return
        self.dragging = True
        self._rect_f = QRectF(self.rect_item.rect())

    def begin_resize(self, direction: str):
        if self.rect_item is None:
            return
        self.resizing = True
        self.resize_direction = direction
        self._rect_f = QRectF(self.rect_item.rect())

    def apply_motion(self, dx: float, dy: float, scale: float, snap_rect_callback=None, show_grid=False):
        if self.rect_item is None or self._rect_f is None:
            return
        new_r = QRectF(self._rect_f)
        if self.dragging:
            new_r.translate(dx, dy)
        elif self.resizing:
            dir_ = self.resize_direction or ""
            if "n" in dir_:
                new_r.setTop(new_r.top() + dy)
            if "s" in dir_:
                new_r.setBottom(new_r.bottom() + dy)
            if "w" in dir_:
                new_r.setLeft(new_r.left() + dx)
            if "e" in dir_:
                new_r.setRight(new_r.right() + dx)
        if new_r.width() >= 10 and new_r.height() >= 10:
            painted = snap_rect_callback(new_r) if show_grid and snap_rect_callback else new_r
            self.rect_item.setRect(painted)
            self._rect_f = new_r

    def finish_interaction(self):
        self.dragging = False
        self.resizing = False
        self.resize_direction = None
        self.update_clipboard()

    def update_clipboard(self):
        if self.rect_item is None:
            return
        r = self.rect_item.rect()
        self.copy_mode_manager.copy_rect((r.left(), r.top(), r.right(), r.bottom()), self.frame_area)
