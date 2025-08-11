"""Screenshot viewer module (refactored).

Cleaned to remove duplicate method definitions and delegate square/bbox/locate/grid & copy logic to sv_utils utilities.
"""

# Clean restored implementation of ScreenshotViewer with square + bbox tools
from __future__ import annotations

import io
import re
from typing import Dict

from PIL import Image
from PyQt6.QtCore import Qt, QTimer, QPoint, QRectF, QEvent
from PyQt6.QtGui import (
    QPixmap,
    QBrush,
    QColor,
    QWheelEvent,
    QMouseEvent,
    QKeyEvent,
    QPen,
    QCursor,
)
from PyQt6.QtWidgets import (
    QWidget,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPixmapItem,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QFrame,
    QGraphicsRectItem,
    QGraphicsEllipseItem,
)

# Utilities
from .sv_utils import (
    CopyModeManager,
    SquareTool,
    BBoxTool,
    create_pixel_grid,
    base_steps,
    parse_coordinates,
    convert_to_scene_coords,
    draw_bbox,
    start_locate_animation,
)

PIXEL_ART_GRID_WIDTH = 192
PIXEL_ART_GRID_HEIGHT = 128


class ScreenshotViewer(QGraphicsView):
    """Screenshot viewer with grid, coordinate banners, locate animation, bbox and 16x16 square tools."""

    _LAST_GEOMETRY = None

    def __init__(self, frame_area: Dict, screenshot: Image.Image):
        super().__init__()
        self.frame_area = frame_area
        self.screenshot = screenshot

        # Scene / pixmap
        self._zoom = 0
        self._empty = True
        self._scene = QGraphicsScene(self)
        self._photo = QGraphicsPixmapItem()
        self._photo.setShapeMode(QGraphicsPixmapItem.ShapeMode.BoundingRectShape)
        self._scene.addItem(self._photo)
        self.setScene(self._scene)

        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QBrush(QColor(30, 30, 30)))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        # Grid
        self.show_grid = False
        self._grid_item = None

        # Locate / animation
        self.locate_items: list = []
        self.locate_state = 0
        self.locate_timer = QTimer()
        self.locate_timer.timeout.connect(self._update_locate_animation)
        self.locate_animation_step = 0
        self.locate_color = QColor(255, 255, 255)
        self.target_x: float | None = None
        self.target_y: float | None = None

        # Tools
        self.copy_mode_manager = CopyModeManager()
        self.square_tool = SquareTool(self._scene, self.frame_area, self.copy_mode_manager)
        self.bbox_tool = BBoxTool(self._scene, self.frame_area, self.copy_mode_manager)
        self.draw_square_mode = False
        self.draw_bbox_mode = False

        # Interaction state
        self._mouse_pressed_pos = QPoint()
        self._last_copied = "----, ----"
        self._last_view_pos = None

        # Load screenshot
        self.original_pixmap = self._pil_to_qpixmap(screenshot)
        self.setPhoto(self.original_pixmap)

        # UI
        self._setup_as_window()

    # ---------------- Utility -----------------
    def _pil_to_qpixmap(self, pil_image: Image.Image) -> QPixmap:
        buffer = io.BytesIO()
        pil_image.save(buffer, format="PNG")
        buffer.seek(0)
        pixmap = QPixmap()
        pixmap.loadFromData(buffer.getvalue())
        return pixmap

    def _setup_as_window(self):
        self.window_widget = QWidget()
        self.window_widget.setWindowTitle("Frame Screenshot Viewer")
        self.window_widget.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.window_widget.resize(1280, 720)
        self.window_widget.setMinimumSize(800, 600)
        if ScreenshotViewer._LAST_GEOMETRY is not None:
            self.window_widget.setGeometry(ScreenshotViewer._LAST_GEOMETRY)
        self.window_widget.installEventFilter(self)

        self.setStyleSheet(
            """
            QWidget { background-color: #1e1e1e; color: #ffffff; }
        """
        )

        layout = QVBoxLayout(self.window_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        banner_style = (
            "QLabel { background-color: #2d2d2d; color: #ffffff; padding: 2px 4px; border-bottom: none;"
            " font-family: 'Consolas', 'Courier New', monospace; font-size: 12pt; }"
        )

        # --- Line 1 ---
        self.header_line1 = QWidget()
        self.header_line1.setStyleSheet("QWidget { background-color: #2d2d2d; }")
        line1_layout = QHBoxLayout(self.header_line1)
        line1_layout.setContentsMargins(2, 1, 2, 1)

        self.frame_info_label = QLabel()
        self.frame_info_label.setStyleSheet(banner_style)
        self.frame_info_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.refresh_screenshot_button = QPushButton("SCREENSHOT")
        self.refresh_screenshot_button.setFixedWidth(90)
        self.refresh_screenshot_button.clicked.connect(self._on_refresh_screenshot_clicked)
        self.refresh_screenshot_button.setStyleSheet(
            """
            QPushButton { background-color: #ff9800; color: white; border: none; padding: 4px 8px; border-radius: 2px; font-weight: bold; font-size: 9pt; }
            QPushButton:hover { background-color: #ffb74d; }
            QPushButton:pressed { background-color: #f57c00; }
        """
        )

        self.copy_mode_button = QPushButton(self.copy_mode_manager.mode)
        self.copy_mode_button.setFixedWidth(110)
        self.copy_mode_button.clicked.connect(self._on_copy_mode_clicked)
        self.copy_mode_button.setStyleSheet(
            """
            QPushButton { background-color: #9c27b0; color: white; border: none; padding: 4px 8px; border-radius: 2px; font-weight: bold; font-size: 9pt; }
            QPushButton:hover { background-color: #ba68c8; }
            QPushButton:pressed { background-color: #7b1fa2; }
        """
        )

        self.draw_bbox_button = QPushButton("Draw BBOX")
        self.draw_bbox_button.setFixedWidth(80)
        self.draw_bbox_button.clicked.connect(self._on_draw_bbox_clicked)
        self.draw_bbox_button.setStyleSheet(
            """
            QPushButton { background-color: #388e3c; color: white; border: none; padding: 4px 8px; border-radius: 2px; font-weight: bold; font-size: 9pt; }
            QPushButton:hover { background-color: #4caf50; }
            QPushButton:pressed { background-color: #2e7d32; }
        """
        )

        line1_layout.addWidget(self.frame_info_label)
        line1_layout.addStretch()
        line1_layout.addWidget(self.refresh_screenshot_button)
        line1_layout.addWidget(self.copy_mode_button)
        line1_layout.addWidget(self.draw_bbox_button)

        # --- Line 2 ---
        self.header_line2 = QWidget()
        self.header_line2.setStyleSheet("QWidget { background-color: #2d2d2d; border-bottom: 1px solid #555555; }")
        line2_layout = QHBoxLayout(self.header_line2)
        line2_layout.setContentsMargins(2, 1, 2, 1)

        self.locate_text_label = QLabel("LOCATE:")
        self.locate_text_label.setStyleSheet(banner_style + "QLabel { font-weight: bold; }")

        self.copied_info_label = QLabel()
        self.copied_info_label.setStyleSheet(banner_style)
        self.copied_info_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.coord_input = QLineEdit()
        self.coord_input.setPlaceholderText("Coordinates (format matches copy mode)")
        self.coord_input.setFixedWidth(200)
        self.coord_input.setStyleSheet(
            """
            QLineEdit { background-color: #3d3d3d; color: #ffffff; border: 1px solid #555; padding: 2px 5px; font-size: 9pt; }
        """
        )

        line2_layout.addWidget(self.copied_info_label)
        line2_layout.addStretch()
        line2_layout.addWidget(self.locate_text_label)
        line2_layout.addWidget(self.coord_input)

        # --- Line 3 ---
        self.header_line3 = QWidget()
        self.header_line3.setFixedHeight(32)
        self.header_line3.setStyleSheet("QWidget { background-color: #2d2d2d; border-bottom: 1px solid #555555; }")
        line3_layout = QHBoxLayout(self.header_line3)
        line3_layout.setContentsMargins(2, 1, 2, 1)

        self.locate_info_label = QLabel("Ready")
        self.locate_info_label.setStyleSheet(banner_style)
        self.locate_info_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        buttons_widget = QWidget()
        buttons_layout = QHBoxLayout(buttons_widget)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(5)

        self.locate_button = QPushButton("LOCATE")
        self.locate_button.setFixedWidth(60)
        self.locate_button.clicked.connect(self._on_locate_clicked)
        self.locate_button.setStyleSheet(
            """
            QPushButton { background-color: #1976d2; color: white; border: none; padding: 4px 8px; border-radius: 2px; font-weight: bold; font-size: 9pt; }
            QPushButton:hover { background-color: #2196f3; }
            QPushButton:pressed { background-color: #0d47a1; }
        """
        )

        self.clear_button = QPushButton("CLEAR")
        self.clear_button.setFixedWidth(50)
        self.clear_button.clicked.connect(self._on_clear_clicked)
        self.clear_button.setStyleSheet(
            """
            QPushButton { background-color: #666666; color: white; border: none; padding: 4px 8px; border-radius: 2px; font-weight: bold; font-size: 9pt; }
            QPushButton:hover { background-color: #777777; }
            QPushButton:pressed { background-color: #555555; }
        """
        )

        buttons_layout.addWidget(self.locate_button)
        buttons_layout.addWidget(self.clear_button)

        divider = QLabel("|")
        divider.setStyleSheet("QLabel { color: #666666; font-weight: bold; margin: 0 3px; }")
        buttons_layout.addWidget(divider)

        self.draw_square_button = QPushButton("16x16")
        self.draw_square_button.setFixedSize(32, 24)
        self.draw_square_button.clicked.connect(self._on_draw_square_clicked)
        self.draw_square_button.setStyleSheet(
            """
            QPushButton { background-color: #e91e63; color: white; border: none; padding: 2px; border-radius: 2px; font-weight: bold; font-size: 8pt; }
            QPushButton:hover { background-color: #f06292; }
            QPushButton:pressed { background-color: #c2185b; }
        """
        )
        buttons_layout.addWidget(self.draw_square_button)

        line3_layout.addWidget(self.locate_info_label)
        line3_layout.addStretch()
        line3_layout.addWidget(buttons_widget)

        # Footer
        self.footer_banner = QLabel()
        self.footer_banner.setFixedHeight(24)
        self.footer_banner.setStyleSheet(
            """
            QLabel { background-color: #2d2d2d; color: #888888; padding: 4px 10px; border-top: 1px solid #555555; font-family: 'Consolas','Courier New', monospace; font-size: 9pt; font-style: italic; }
        """
        )

        layout.addWidget(self.header_line1)
        layout.addWidget(self.header_line2)
        layout.addWidget(self.header_line3)
        layout.addWidget(self)
        layout.addWidget(self.footer_banner)

        self._update_info_banner()
        self._update_footer_banner()
        self.window_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # --------------- Event Filter ---------------
    def eventFilter(self, obj, event):
        if obj is self.window_widget and event.type() in (QEvent.Type.Close, QEvent.Type.Hide):
            try:
                ScreenshotViewer._LAST_GEOMETRY = self.window_widget.geometry()
            except Exception:
                pass
        return super().eventFilter(obj, event)

    # ---------------- Public API -----------------
    def show(self):  # pragma: no cover (UI)
        self.window_widget.show()

    def hasPhoto(self):
        return not self._empty

    def resetView(self, scale=1):
        rect = QRectF(self._photo.pixmap().rect())
        if rect.isNull():
            return
        overpan = 75
        expanded = rect.adjusted(-overpan, -overpan, overpan, overpan)
        self.setSceneRect(expanded)
        if (scale := max(1, scale)) == 1:
            self._zoom = 0
        if self.hasPhoto():
            unity = self.transform().mapRect(QRectF(0, 0, 1, 1))
            self.scale(1 / unity.width(), 1 / unity.height())
            vp = self.viewport()
            if vp:
                viewrect = vp.rect()
                scenerect = self.transform().mapRect(rect)
                factor = min(viewrect.width() / scenerect.width(), viewrect.height() / scenerect.height()) * scale
                self.scale(factor, factor)
                self.centerOn(self._photo)

    def setPhoto(self, pixmap=None):
        if pixmap and not pixmap.isNull():
            self._empty = False
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self._photo.setPixmap(pixmap)
            rect = QRectF(pixmap.rect())
            overpan = 75
            self.setSceneRect(rect.adjusted(-overpan, -overpan, overpan, overpan))
        else:
            self._empty = True
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self._photo.setPixmap(QPixmap())
        self._zoom = 0
        self.resetView()

    def zoom(self, step):
        scale_factor = 1.25
        zoom = max(0, self._zoom + int(step))
        if zoom != self._zoom:
            step_dir = 1 if zoom > self._zoom else -1
            self._zoom = zoom
            if self._zoom > 0:
                factor = scale_factor**step_dir
                self.scale(factor, factor)
            else:
                self.resetView()
            self._update_grid()
            self._update_info_banner()

    def wheelEvent(self, event: QWheelEvent):  # pragma: no cover (UI)
        if self.hasPhoto():
            delta = event.angleDelta().y()
            self.zoom(delta and delta // abs(delta))

    def resizeEvent(self, event):  # pragma: no cover (UI)
        super().resizeEvent(event)
        if self.hasPhoto():
            self.resetView()

    # ---------------- Coordinate banners -----------------
    def updateCoordinates(self, pos=None):
        if self._photo.isUnderMouse():
            if pos is None:
                pos = self.mapFromGlobal(QCursor.pos())
            scene_pos = self.mapToScene(pos)
            point = QPoint(int(scene_pos.x()), int(scene_pos.y()))
        else:
            point = QPoint()
        self._on_coordinates_changed(point)

    def _on_coordinates_changed(self, point: QPoint):
        if not point.isNull():
            px = int(point.x())
            py = int(point.y())
            fx = self.frame_area.get("x", 0)
            fy = self.frame_area.get("y", 0)
            fw = self.frame_area.get("width", 1)
            fh = self.frame_area.get("height", 1)
            sx = fx + px
            sy = fy + py
            xp = max(0, min(100, (px / fw) * 100))
            yp = max(0, min(100, (py / fh) * 100))
            txt = f" MOUSE || Screen Coords: {sx:>5}, {sy:>4} | Frame Coords: {px:>4}, {py:>4} | Frame %: {xp:>7.4f}%, {yp:>7.4f}%"
        else:
            txt = " MOUSE || Screen Coords: -----, ---- | Frame Coords: ----, ---- | Frame %: --.----%, --.----%"
        self.frame_info_label.setText(txt)
        self.copied_info_label.setText(self._get_copied_display())
        self.locate_info_label.setText(self._get_locate_display())

    def _get_copied_display(self):
        try:
            parts = self._last_copied.replace(" ", "").split(",")
            if len(parts) == 2:
                fx = self.frame_area.get("x", 0)
                fy = self.frame_area.get("y", 0)
                fw = self.frame_area.get("width", 1)
                fh = self.frame_area.get("height", 1)
                cx = int(parts[0])
                cy = int(parts[1])
                sx = fx + cx
                sy = fy + cy
                xp = max(0, min(100, (cx / fw) * 100))
                yp = max(0, min(100, (cy / fh) * 100))
                return f"COPIED || Screen Coords: {sx:>5}, {sy:>4} | Frame Coords: {cx:>4}, {cy:>4} | Frame %: {xp:>7.4f}%, {yp:>7.4f}%"
            if len(parts) == 4:
                x1, y1, x2, y2 = map(int, parts)
                fx = self.frame_area.get("x", 0)
                fy = self.frame_area.get("y", 0)
                return f"COPIED || BBOX: Frame({x1:>4},{y1:>4},{x2:>4},{y2:>4}) | Screen({fx + x1:>4},{fy + y1:>4},{fx + x2:>4},{fy + y2:>4})"
        except Exception:
            pass
        return "COPIED || Screen Coords: -----, ---- | Frame Coords: ----, ---- | Frame %:  --.----%, --.----%"

    def _get_locate_display(self):
        if hasattr(self, "target_x") and hasattr(self, "target_y") and self.locate_state > 0:
            fx = self.frame_area.get("x", 0)
            fy = self.frame_area.get("y", 0)
            fw = self.frame_area.get("width", 1)
            fh = self.frame_area.get("height", 1)
            tx = float(getattr(self, "target_x", 0))
            ty = float(getattr(self, "target_y", 0))
            sx = fx + int(tx)
            sy = fy + int(ty)
            xp = max(0, min(100, (tx / fw) * 100))
            yp = max(0, min(100, (ty / fh) * 100))
            return f"LOCATE || Screen Coords: {sx:>5}, {sy:>4} | Frame Coords: {int(tx):>4}, {int(ty):>4} | Frame %: {xp:>7.4f}%, {yp:>7.4f}%"
        return "LOCATE || Screen Coords: -----, ---- | Frame Coords: ----, ---- | Frame %: --.----%, --.----%"

    def _update_footer_banner(self):
        frame_size = f"Frame: {self.frame_area.get('x', 0):>4}, {self.frame_area.get('y', 0):>4} | Size: {self.frame_area.get('width', 0):>4}x{self.frame_area.get('height', 0):>4}"
        grid_zoom = f"Grid: {'ON ' if self.show_grid else 'OFF'} | Zoom: {self._zoom:>2}x"
        self.footer_banner.setText(
            "Instructions: Mouse: Wheel=Zoom, Drag=Pan, Right=Grid, Left=Copy, F=Fit                    "
            f"{frame_size}                    {grid_zoom}"
        )

    def _update_info_banner(self):
        self._on_coordinates_changed(QPoint())
        self._update_footer_banner()

    # ---------------- Actions -----------------
    def _on_refresh_screenshot_clicked(self):  # pragma: no cover
        try:
            from PIL import ImageGrab

            fx = self.frame_area.get("x", 0)
            fy = self.frame_area.get("y", 0)
            fw = self.frame_area.get("width", 0)
            fh = self.frame_area.get("height", 0)
            if fw <= 0 or fh <= 0:
                return
            bbox = (fx, fy, fx + fw, fy + fh)
            new_img = ImageGrab.grab(bbox=bbox, all_screens=True)
            self.screenshot = new_img
            self.original_pixmap = self._pil_to_qpixmap(new_img)
            self.setPhoto(self.original_pixmap)
            self._clear_locate()
            self.locate_state = 0
        except Exception:
            pass

    def _on_copy_mode_clicked(self):
        self.copy_mode_button.setText(self.copy_mode_manager.cycle())

    # Square tool toggle
    def _on_draw_square_clicked(self):
        self.draw_square_mode = not self.draw_square_mode
        if self.draw_square_mode:
            if self.draw_bbox_mode:
                self._on_draw_bbox_clicked()
            # Allow panning except while actively dragging/resizing square
            self.draw_square_button.setText("Done")
            if self.hasPhoto() and self.square_tool.rect_item is None:
                pm = self._photo.pixmap()
                if not pm.isNull():
                    self.square_tool.create_initial(pm.width(), pm.height(), self.transform().m11())
                    if self.square_tool.rect_item:
                        r = self.square_tool.rect_item.rect()
                        self._last_copied = f"{int(r.left())},{int(r.top())},{int(r.right())},{int(r.bottom())}"
        else:
            self.draw_square_button.setText("16x16")
            self.square_tool.clear()
            # Restore pan mode when square mode exits
            if self.hasPhoto():
                self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    # BBOX tool toggle
    def _on_draw_bbox_clicked(self):
        self.draw_bbox_mode = not self.draw_bbox_mode
        if self.draw_bbox_mode:
            if self.draw_square_mode:
                self._on_draw_square_clicked()
            self.draw_bbox_button.setText("Done")
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            if self.bbox_tool.rect_item is None and self.hasPhoto():
                pm = self._photo.pixmap()
                if not pm.isNull():
                    self.bbox_tool.ensure_created(pm.width(), pm.height())
        else:
            self.draw_bbox_button.setText("Draw BBOX")
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    # Locate
    def _on_locate_clicked(self):
        try:
            text = self.coord_input.text().strip()
            if not text:
                self.locate_info_label.setText("Enter coordinates")
                return
            parsed = parse_coordinates(text, self.copy_mode_manager.mode, self.frame_area)
            if not parsed:
                self.locate_info_label.setText("Bad format")
                return
            self._clear_locate()
            if parsed["type"] == "point":
                sx, sy = convert_to_scene_coords(parsed["x"], parsed["y"], self.copy_mode_manager.mode, self.frame_area)
                self.locate_state = 1
                self.locate_animation_step = 0
                start_locate_animation(self, sx, sy, self.screenshot)
            else:
                x1, y1 = convert_to_scene_coords(
                    parsed["x1"], parsed["y1"], self.copy_mode_manager.mode, self.frame_area
                )
                x2, y2 = convert_to_scene_coords(
                    parsed["x2"], parsed["y2"], self.copy_mode_manager.mode, self.frame_area
                )
                rect = draw_bbox(self._scene, x1, y1, x2, y2)
                self.locate_items.append(rect)
                self.locate_info_label.setText(f"BBox: {int(x1)},{int(y1)} to {int(x2)},{int(y2)}")
        except Exception as e:
            self.locate_info_label.setText(f"Error: {e}")

    def _on_clear_clicked(self):  # pragma: no cover
        self._clear_locate()
        self.locate_state = 0
        self.locate_button.setText("LOCATE")

    # ---------------- Mouse / Key Events -----------------
    def mousePressEvent(self, event: QMouseEvent):  # pragma: no cover
        if event.button() == Qt.MouseButton.RightButton:
            self.show_grid = not self.show_grid
            self._update_grid()
            super().mousePressEvent(event)
            return
        if event.button() == Qt.MouseButton.LeftButton:
            if self.draw_square_mode and self.square_tool.rect_item and self.hasPhoto():
                scene_pos = self.mapToScene(event.position().toPoint())
                direction = self.square_tool.detect_resize_direction(scene_pos, max(1e-6, self.transform().m11()))
                if direction:
                    self.square_tool.begin_resize(direction)
                    self._last_view_pos = event.position()
                    self.setDragMode(QGraphicsView.DragMode.NoDrag)
                elif self.square_tool.rect_item.contains(self.square_tool.rect_item.mapFromScene(scene_pos)):
                    self.square_tool.begin_drag(scene_pos)
                    self._last_view_pos = event.position()
                    self.setDragMode(QGraphicsView.DragMode.NoDrag)
                else:
                    # Click outside square => enable panning
                    self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            elif self.draw_bbox_mode and self.bbox_tool.rect_item and self.hasPhoto():
                scene_pos = self.mapToScene(event.position().toPoint())
                direction = self.bbox_tool.detect_resize_direction(scene_pos, max(1e-6, self.transform().m11()))
                if direction:
                    self.bbox_tool.begin_resize(direction)
                    self._last_view_pos = event.position()
                    self.setDragMode(QGraphicsView.DragMode.NoDrag)
                elif self.bbox_tool.rect_item.contains(self.bbox_tool.rect_item.mapFromScene(scene_pos)):
                    self.bbox_tool.begin_drag()
                    self._last_view_pos = event.position()
                    self.setDragMode(QGraphicsView.DragMode.NoDrag)
                else:
                    # Click outside bbox => enable panning
                    self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            else:
                # No tool active or no tool rect => enable panning
                self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
                self._mouse_pressed_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):  # pragma: no cover
        scale = max(1e-6, self.transform().m11())
        if self.draw_square_mode and (self.square_tool.dragging or self.square_tool.resizing):
            current = event.position()
            if self._last_view_pos is None:
                self._last_view_pos = current
            dx_vp = current.x() - self._last_view_pos.x()
            dy_vp = current.y() - self._last_view_pos.y()
            self.square_tool.apply_motion(dx_vp / scale, dy_vp / scale, scale)
            self._last_view_pos = current
        elif self.draw_bbox_mode and (self.bbox_tool.dragging or self.bbox_tool.resizing):
            current = event.position()
            if self._last_view_pos is None:
                self._last_view_pos = current
            dx_vp = current.x() - self._last_view_pos.x()
            dy_vp = current.y() - self._last_view_pos.y()
            self.bbox_tool.apply_motion(
                dx_vp / scale,
                dy_vp / scale,
                scale,
                snap_rect_callback=self._snap_rect_to_grid,
                show_grid=self.show_grid,
            )
            self._last_view_pos = current
        else:
            if self.draw_square_mode and self.square_tool.rect_item:
                scene_pos = self.mapToScene(event.position().toPoint())
                direction = self.square_tool.detect_resize_direction(scene_pos, scale)
                if direction:
                    self.setCursor(self._get_resize_cursor(direction))
                elif self.square_tool.rect_item.contains(self.square_tool.rect_item.mapFromScene(scene_pos)):
                    self.setCursor(Qt.CursorShape.SizeAllCursor)
                else:
                    self.setCursor(Qt.CursorShape.ArrowCursor)
            elif self.draw_bbox_mode and self.bbox_tool.rect_item:
                scene_pos = self.mapToScene(event.position().toPoint())
                direction = self.bbox_tool.detect_resize_direction(scene_pos, scale)
                if direction:
                    self.setCursor(self._get_resize_cursor(direction))
                elif self.bbox_tool.rect_item.contains(self.bbox_tool.rect_item.mapFromScene(scene_pos)):
                    self.setCursor(Qt.CursorShape.SizeAllCursor)
                else:
                    self.setCursor(Qt.CursorShape.ArrowCursor)
            else:
                # Ensure panning remains enabled when not manipulating
                if self.hasPhoto() and self.dragMode() != QGraphicsView.DragMode.ScrollHandDrag:
                    self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
                self.setCursor(Qt.CursorShape.ArrowCursor)
        if not (
            (self.draw_bbox_mode and self.bbox_tool.dragging) or (self.draw_square_mode and self.square_tool.dragging)
        ):
            self.updateCoordinates(event.position().toPoint())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):  # pragma: no cover
        if event.button() == Qt.MouseButton.LeftButton:
            if self.draw_square_mode and (self.square_tool.dragging or self.square_tool.resizing):
                self.square_tool.finish_interaction()
                if self.square_tool.rect_item:
                    r = self.square_tool.rect_item.rect()
                    self._last_copied = f"{int(r.left())},{int(r.top())},{int(r.right())},{int(r.bottom())}"
                self._update_info_banner()
                self._last_view_pos = None
                # Re-enable panning after manipulation
                if self.hasPhoto():
                    self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            elif self.draw_bbox_mode and (self.bbox_tool.dragging or self.bbox_tool.resizing):
                self.bbox_tool.finish_interaction()
                if self.bbox_tool.rect_item:
                    r = self.bbox_tool.rect_item.rect()
                    self._last_copied = f"{int(r.left())},{int(r.top())},{int(r.right())},{int(r.bottom())}"
                self._update_info_banner()
                self._last_view_pos = None
                if self.hasPhoto():
                    self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            elif not self.draw_bbox_mode and not self.draw_square_mode and self.hasPhoto():
                release_pos = event.position().toPoint()
                delta = release_pos - self._mouse_pressed_pos
                if abs(delta.x()) <= 3 and abs(delta.y()) <= 3:
                    scene_pos = self.mapToScene(release_pos)
                    pm = self._photo.pixmap()
                    if not pm.isNull() and QRectF(0, 0, pm.width(), pm.height()).contains(scene_pos):
                        self.copy_mode_manager.copy_point(scene_pos.x(), scene_pos.y(), self.frame_area)
                        self._last_copied = f"{int(scene_pos.x()):>4}, {int(scene_pos.y()):>4}"
                        self._update_info_banner()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent):  # pragma: no cover
        if event.key() == Qt.Key.Key_F:
            self.resetView()
            self._update_info_banner()
        else:
            super().keyPressEvent(event)

    # ---------------- Grid -----------------
    def _base_steps(self):
        return base_steps(self.frame_area)

    def _update_grid(self):
        if self._grid_item:
            self._scene.removeItem(self._grid_item)
            self._grid_item = None
        if self.show_grid and self.hasPhoto():
            pm = self._photo.pixmap()
            if not pm.isNull():
                # Compute grid anchored at frame (0,0) relative to screenshot regardless of window origin
                grid = create_pixel_grid(pm.width(), pm.height(), self.frame_area, self.transform().m11())
                if grid:
                    # Ensure grid placed at (0,0); do not inherit any transformation offset
                    grid.setPos(0, 0)
                    self._grid_item = grid
                    self._scene.addItem(self._grid_item)
        self._update_footer_banner()

    def _snap_rect_to_grid(self, rect: QRectF) -> QRectF:
        if not self.show_grid:
            return QRectF(rect)
        step_x, step_y = self._base_steps()
        if step_x <= 0 or step_y <= 0:
            return QRectF(rect)
        left_val = round(rect.left() / step_x) * step_x
        top_val = round(rect.top() / step_y) * step_y
        right_val = round(rect.right() / step_x) * step_x
        bottom_val = round(rect.bottom() / step_y) * step_y
        if left_val > right_val:
            left_val, right_val = right_val, left_val
        if top_val > bottom_val:
            top_val, bottom_val = bottom_val, top_val
        return QRectF(left_val, top_val, right_val - left_val, bottom_val - top_val)

    # ---------------- Locate Animation -----------------
    def _update_locate_animation(self):  # pragma: no cover
        for item in self.locate_items:
            self._scene.removeItem(item)
        self.locate_items.clear()
        tx = self.target_x if self.target_x is not None else None
        ty = self.target_y if self.target_y is not None else None
        if tx is None or ty is None:
            return
        max_radius = 30
        total_steps = 10
        cur_radius = max_radius - (self.locate_animation_step * max_radius / total_steps)
        if cur_radius <= 1:
            self._stop_locate_animation()
            self._highlight_single_pixel()
            return
        circle = QGraphicsEllipseItem(
            tx - cur_radius,
            ty - cur_radius,
            cur_radius * 2,
            cur_radius * 2,
        )
        pen = QPen(self.locate_color)
        pen.setWidth(2)
        pen.setCosmetic(True)
        circle.setPen(pen)
        circle.setBrush(QBrush())
        self._scene.addItem(circle)
        self.locate_items.append(circle)
        self.locate_animation_step += 1

    def _stop_locate_animation(self):  # pragma: no cover
        self.locate_timer.stop()
        for item in self.locate_items:
            self._scene.removeItem(item)
        self.locate_items.clear()

    def _highlight_single_pixel(self):  # pragma: no cover
        tx = self.target_x if self.target_x is not None else None
        ty = self.target_y if self.target_y is not None else None
        if tx is None or ty is None:
            return
        px_rect = QGraphicsRectItem(tx, ty, 1, 1)
        px_rect.setPen(QPen(Qt.PenStyle.NoPen))
        px_rect.setBrush(QBrush(self.locate_color))
        self._scene.addItem(px_rect)
        self.locate_items.append(px_rect)

    def _clear_locate(self):
        for item in self.locate_items:
            self._scene.removeItem(item)
        self.locate_items.clear()
        if self.locate_timer.isActive():
            self.locate_timer.stop()

    # ---------------- Copy / Cursor Helpers -----------------
    def _get_resize_cursor(self, direction):
        return {
            "nw": Qt.CursorShape.SizeFDiagCursor,
            "ne": Qt.CursorShape.SizeBDiagCursor,
            "sw": Qt.CursorShape.SizeBDiagCursor,
            "se": Qt.CursorShape.SizeFDiagCursor,
            "n": Qt.CursorShape.SizeVerCursor,
            "s": Qt.CursorShape.SizeVerCursor,
            "w": Qt.CursorShape.SizeHorCursor,
            "e": Qt.CursorShape.SizeHorCursor,
        }.get(direction, Qt.CursorShape.ArrowCursor)
