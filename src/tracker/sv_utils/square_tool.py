from __future__ import annotations
from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QColor, QPen, QBrush
from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsItemGroup, QGraphicsLineItem
from .grid import base_steps


class SquareTool:
    def __init__(self, scene, frame_area: dict, copy_mode_manager):
        self.scene = scene
        self.frame_area = frame_area
        self.copy_mode_manager = copy_mode_manager
        self.rect_item: QGraphicsRectItem | None = None
        self.grid_item: QGraphicsItemGroup | None = None
        self.handles = []
        self.dragging = False
        self.resizing = False
        self.resize_direction = None
        self._rect_f: QRectF | None = None

    def create_initial(self, pixmap_width: int, pixmap_height: int, transform_scale: float):
        step_x, step_y = base_steps(self.frame_area)
        unit = min(step_x, step_y)
        size = unit * 16
        left = pixmap_width / 2 - size / 2
        top = pixmap_height / 2 - size / 2
        self.rect_item = QGraphicsRectItem(left, top, size, size)
        pen = QPen(QColor(233, 30, 99))
        pen.setWidth(2)
        pen.setCosmetic(True)
        self.rect_item.setPen(pen)
        self.rect_item.setBrush(QBrush())
        self.scene.addItem(self.rect_item)
        self._rect_f = QRectF(left, top, size, size)
        self._rebuild_grid()
        self._rebuild_handles(transform_scale)
        self.update_clipboard()

    def clear(self):
        if self.rect_item:
            self.scene.removeItem(self.rect_item)
            self.rect_item = None
        if self.grid_item:
            self.scene.removeItem(self.grid_item)
            self.grid_item = None
        for h in self.handles:
            self.scene.removeItem(h)
        self.handles = []
        self.dragging = False
        self.resizing = False
        self.resize_direction = None
        self._rect_f = None

    def _rebuild_grid(self):
        if not self.rect_item:
            return
        if self.grid_item:
            self.scene.removeItem(self.grid_item)
            self.grid_item = None
        r = self.rect_item.rect()
        group = QGraphicsItemGroup()
        pen = QPen(QColor(233, 30, 99, 100))
        pen.setWidth(1)
        pen.setCosmetic(True)
        step = r.width() / 16
        for i in range(17):
            x = r.left() + i * step
            ln = QGraphicsLineItem(x, r.top(), x, r.bottom())
            ln.setPen(pen)
            group.addToGroup(ln)
        for i in range(17):
            y = r.top() + i * step
            ln = QGraphicsLineItem(r.left(), y, r.right(), y)
            ln.setPen(pen)
            group.addToGroup(ln)
        self.grid_item = group
        self.scene.addItem(group)

    def _rebuild_handles(self, scale: float):
        if not self.rect_item:
            return
        for h in self.handles:
            self.scene.removeItem(h)
        self.handles = []
        r = self.rect_item.rect()
        handle_size = max(6, 10 / max(0.5, scale))
        # Only corner handles retained for resize (edges optional)
        corners = [
            (r.topLeft(), "nw"),
            (r.topRight(), "ne"),
            (r.bottomLeft(), "sw"),
            (r.bottomRight(), "se"),
        ]
        for pt, tag in corners:
            h = QGraphicsRectItem(pt.x() - handle_size / 2, pt.y() - handle_size / 2, handle_size, handle_size)
            h.setPen(QPen())
            h.setBrush(QBrush())
            h.setData(0, tag)
            self.scene.addItem(h)
            self.handles.append(h)

    def detect_resize_direction(self, scene_pos, scale: float):
        if not self.rect_item:
            return None
        r = self.rect_item.rect()
        corner_thr = max(6, 10 / max(0.5, scale))
        for pt, d in [
            (r.topLeft(), "nw"),
            (r.topRight(), "ne"),
            (r.bottomLeft(), "sw"),
            (r.bottomRight(), "se"),
        ]:
            if (scene_pos - pt).manhattanLength() <= corner_thr * 2:
                return d
        return None

    def begin_drag(self, scene_pos):
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

    def apply_motion(self, dx: float, dy: float, scale: float):
        if self.rect_item is None or self._rect_f is None:
            return
        new_r = QRectF(self._rect_f)
        if self.dragging:
            new_r.translate(dx, dy)
        elif self.resizing:
            dir_ = self.resize_direction or ""
            if dir_ in ("e", "w"):
                primary = dx if dir_ == "e" else -dx
            elif dir_ in ("n", "s"):
                primary = -dy if dir_ == "n" else dy
            else:
                cand_x = dx if "e" in dir_ else -dx
                cand_y = dy if "s" in dir_ else -dy
                primary = cand_x if abs(cand_x) > abs(cand_y) else cand_y
            size = max(new_r.width(), new_r.height()) + primary
            min_size = 4
            size = max(min_size, size)
            if dir_ == "n":
                cx = new_r.center().x()
                new_r.setTop(new_r.bottom() - size)
                new_r.setLeft(cx - size / 2)
                new_r.setRight(cx + size / 2)
            elif dir_ == "s":
                cx = new_r.center().x()
                new_r.setBottom(new_r.top() + size)
                new_r.setLeft(cx - size / 2)
                new_r.setRight(cx + size / 2)
            elif dir_ == "w":
                cy = new_r.center().y()
                new_r.setLeft(new_r.right() - size)
                new_r.setTop(cy - size / 2)
                new_r.setBottom(cy + size / 2)
            elif dir_ == "e":
                cy = new_r.center().y()
                new_r.setRight(new_r.left() + size)
                new_r.setTop(cy - size / 2)
                new_r.setBottom(cy + size / 2)
            elif dir_ == "nw":
                new_r.setTop(new_r.bottom() - size)
                new_r.setLeft(new_r.right() - size)
            elif dir_ == "ne":
                new_r.setTop(new_r.bottom() - size)
                new_r.setRight(new_r.left() + size)
            elif dir_ == "sw":
                new_r.setBottom(new_r.top() + size)
                new_r.setLeft(new_r.right() - size)
            elif dir_ == "se":
                new_r.setBottom(new_r.top() + size)
                new_r.setRight(new_r.left() + size)
        self.rect_item.setRect(new_r)
        self._rect_f = new_r
        self._rebuild_grid()
        self._rebuild_handles(scale)

    def finish_interaction(self):
        self.dragging = False
        self.resizing = False
        self.resize_direction = None
        self.update_clipboard()

    def update_clipboard(self):
        if not self.rect_item:
            return
        r = self.rect_item.rect()
        self.copy_mode_manager.copy_rect((r.left(), r.top(), r.right(), r.bottom()), self.frame_area)
