#!/usr/bin/env python3
"""
Screenshot viewer component for Widget Window Spy.
Provides professional screenshot analysis with coordinate tracking and bbox editing.
"""

import io
from typing import Dict

from PIL import Image
from PyQt6.QtCore import Qt, QPoint, QPointF, QRectF, QTimer
from PyQt6.QtGui import QBrush, QColor, QCursor, QKeyEvent, QMouseEvent, QPixmap, QPen, QWheelEvent
from PyQt6.QtWidgets import (
    QGraphicsItemGroup,
    QGraphicsLineItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.constants import (
    FONT_FAMILY,
    COLOR_BACKGROUND_PRIMARY,
    COLOR_BACKGROUND_SECONDARY,
    COLOR_TEXT_PRIMARY,
    COLOR_BORDER,
    ZOOM_SCALE_FACTOR,
    OVERPAN_PIXELS,
)


class ScreenshotViewer(QGraphicsView):
    """
    Professional screenshot viewer with coordinate tracking and bbox editing.
    Features zoom, pan, grid overlay, coordinate copying, and locate functionality.
    """

    def __init__(self, frame_area: Dict, screenshot: Image.Image):
        super().__init__()
        self.frame_area = frame_area
        self.screenshot = screenshot

        # Graphics view setup
        self._zoom = 0
        self._empty = True
        self._scene = QGraphicsScene(self)
        self._photo = QGraphicsPixmapItem()
        self._photo.setShapeMode(QGraphicsPixmapItem.ShapeMode.BoundingRectShape)
        self._scene.addItem(self._photo)
        self.setScene(self._scene)

        # View configuration
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QBrush(QColor(30, 30, 30)))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        # Grid system
        self.show_grid = False
        self._grid_item = None

        # Locate functionality
        self.locate_items = []
        self.locate_state = 0
        self.locate_timer = QTimer()
        self.locate_timer.timeout.connect(self._update_locate_animation)
        self.locate_animation_step = 0

        # Target coordinates for locate functionality (set externally)
        self.target_x: float = 0.0
        self.target_y: float = 0.0

        # Bbox editing
        self.draw_bbox_mode = False
        self.bbox_rect_item = None
        self.bbox_handles = []
        self.bbox_dragging = False
        self.bbox_resizing = False
        self.bbox_resize_handle = None
        self.bbox_last_pos = None

        # Click tracking
        self._mouse_pressed_pos = QPoint()
        self._last_copied = "----, ----"

        # Setup interface
        self.original_pixmap = self._pil_to_qpixmap(screenshot)
        self.setPhoto(self.original_pixmap)
        self._setup_as_window()

    def _pil_to_qpixmap(self, pil_image: Image.Image) -> QPixmap:
        """Convert PIL Image to QPixmap efficiently."""
        buffer = io.BytesIO()
        pil_image.save(buffer, format="PNG")
        buffer.seek(0)
        pixmap = QPixmap()
        pixmap.loadFromData(buffer.getvalue())
        return pixmap

    def _setup_as_window(self) -> None:
        """Setup as standalone window with professional interface."""
        # Create wrapper widget
        self.window_widget = QWidget()
        self.window_widget.setWindowTitle("Frame Screenshot Viewer")
        self.window_widget.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.window_widget.resize(1280, 720)
        self.window_widget.setMinimumSize(800, 600)

        # Apply dark theme
        self.window_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {COLOR_BACKGROUND_PRIMARY};
                color: {COLOR_TEXT_PRIMARY};
            }}
        """)

        layout = QVBoxLayout(self.window_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create header sections
        self._create_header_sections(layout)

        # Add main viewer
        layout.addWidget(self)

        # Create footer
        self._create_footer(layout)

        # Initialize displays
        self._update_info_banner()
        self._update_footer_banner()
        self.window_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _create_header_sections(self, layout: QVBoxLayout) -> None:
        """Create header sections with coordinate displays and controls."""
        banner_style = f"""
            QLabel {{
                background-color: {COLOR_BACKGROUND_SECONDARY};
                color: {COLOR_TEXT_PRIMARY};
                padding: 2px 4px;
                border-bottom: none;
                font-family: {FONT_FAMILY};
                font-size: 12pt;
            }}
        """

        # Header Line 1: Frame info + Draw BBOX button
        self.header_line1 = QWidget()
        self.header_line1.setStyleSheet(f"QWidget {{ background-color: {COLOR_BACKGROUND_SECONDARY}; }}")
        line1_layout = QHBoxLayout(self.header_line1)
        line1_layout.setContentsMargins(2, 1, 2, 1)

        self.frame_info_label = QLabel()
        self.frame_info_label.setStyleSheet(banner_style)

        self.draw_bbox_button = QPushButton("Draw BBOX")
        self.draw_bbox_button.setFixedWidth(80)
        self.draw_bbox_button.clicked.connect(self._on_draw_bbox_clicked)
        self.draw_bbox_button.setStyleSheet("""
            QPushButton {
                background-color: #388e3c;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 2px;
                font-weight: bold;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #4caf50;
            }
        """)

        line1_layout.addWidget(self.frame_info_label)
        line1_layout.addStretch()
        line1_layout.addWidget(self.draw_bbox_button)

        # Header Line 2: Copied info + Locate input
        self.header_line2 = QWidget()
        self.header_line2.setStyleSheet(
            f"QWidget {{ background-color: {COLOR_BACKGROUND_SECONDARY}; border-bottom: 1px solid {COLOR_BORDER}; }}"
        )
        line2_layout = QHBoxLayout(self.header_line2)
        line2_layout.setContentsMargins(2, 1, 2, 1)

        self.copied_info_label = QLabel()
        self.copied_info_label.setStyleSheet(banner_style)

        self.locate_text_label = QLabel("LOCATE:")
        self.locate_text_label.setStyleSheet(banner_style + "QLabel { font-weight: bold; }")

        self.coord_input = QLineEdit()
        self.coord_input.setPlaceholderText("100,200 or 0.5,0.75 or 10,20,30,40")
        self.coord_input.setFixedWidth(200)
        self.coord_input.setStyleSheet("""
            QLineEdit {
                background-color: #3d3d3d;
                color: #ffffff;
                border: 1px solid #555;
                padding: 2px 5px;
                font-size: 9pt;
            }
        """)

        line2_layout.addWidget(self.copied_info_label)
        line2_layout.addStretch()
        line2_layout.addWidget(self.locate_text_label)
        line2_layout.addWidget(self.coord_input)

        # Header Line 3: Locate status + buttons
        self.header_line3 = QWidget()
        self.header_line3.setFixedHeight(32)
        self.header_line3.setStyleSheet(
            f"QWidget {{ background-color: {COLOR_BACKGROUND_SECONDARY}; border-bottom: 1px solid {COLOR_BORDER}; }}"
        )
        line3_layout = QHBoxLayout(self.header_line3)
        line3_layout.setContentsMargins(2, 1, 2, 1)

        self.locate_info_label = QLabel("Ready")
        self.locate_info_label.setStyleSheet(banner_style)

        # Control buttons
        buttons_widget = QWidget()
        buttons_layout = QHBoxLayout(buttons_widget)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(5)

        self.locate_button = QPushButton("LOCATE")
        self.locate_button.setFixedWidth(60)
        self.locate_button.clicked.connect(self._on_locate_clicked)
        self.locate_button.setStyleSheet("""
            QPushButton {
                background-color: #1976d2;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 2px;
                font-weight: bold;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #2196f3;
            }
        """)

        self.clear_button = QPushButton("CLEAR")
        self.clear_button.setFixedWidth(50)
        self.clear_button.clicked.connect(self._on_clear_clicked)
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: #666666;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 2px;
                font-weight: bold;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #777777;
            }
        """)

        buttons_layout.addWidget(self.locate_button)
        buttons_layout.addWidget(self.clear_button)

        line3_layout.addWidget(self.locate_info_label)
        line3_layout.addStretch()
        line3_layout.addWidget(buttons_widget)

        layout.addWidget(self.header_line1)
        layout.addWidget(self.header_line2)
        layout.addWidget(self.header_line3)

    def _create_footer(self, layout: QVBoxLayout) -> None:
        """Create footer with instructions and status info."""
        self.footer_banner = QLabel()
        self.footer_banner.setFixedHeight(24)
        self.footer_banner.setStyleSheet(f"""
            QLabel {{
                background-color: {COLOR_BACKGROUND_SECONDARY};
                color: #888888;
                padding: 4px 10px;
                border-top: 1px solid {COLOR_BORDER};
                font-family: {FONT_FAMILY};
                font-size: 9pt;
                font-style: italic;
            }}
        """)
        layout.addWidget(self.footer_banner)

    def show(self) -> None:
        """Show the window widget."""
        self.window_widget.show()

    def hasPhoto(self) -> bool:
        """Check if photo is loaded."""
        return not self._empty

    def setPhoto(self, pixmap: QPixmap | None = None) -> None:
        """Set the photo pixmap."""
        if pixmap and not pixmap.isNull():
            self._empty = False
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self._photo.setPixmap(pixmap)
            rect = QRectF(pixmap.rect())
            expanded_rect = rect.adjusted(-OVERPAN_PIXELS, -OVERPAN_PIXELS, OVERPAN_PIXELS, OVERPAN_PIXELS)
            self.setSceneRect(expanded_rect)
        else:
            self._empty = True
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self._photo.setPixmap(QPixmap())
        self._zoom = 0
        self.resetView()

    def resetView(self, scale: int = 1) -> None:
        """Reset view to fit photo."""
        if not self.hasPhoto():
            return

        rect = QRectF(self._photo.pixmap().rect())
        if rect.isNull():
            return

        overpan_pixels = OVERPAN_PIXELS
        expanded_rect = rect.adjusted(-overpan_pixels, -overpan_pixels, overpan_pixels, overpan_pixels)
        self.setSceneRect(expanded_rect)

        scale = max(1, scale)
        if scale == 1:
            self._zoom = 0

        unity = self.transform().mapRect(QRectF(0, 0, 1, 1))
        self.scale(1 / unity.width(), 1 / unity.height())

        viewport = self.viewport()
        if viewport:
            viewrect = viewport.rect()
            scenerect = self.transform().mapRect(rect)
            factor = min(viewrect.width() / scenerect.width(), viewrect.height() / scenerect.height()) * scale
            self.scale(factor, factor)
            self.centerOn(self._photo)

    def zoom(self, step: int) -> None:
        """Zoom in or out by step amount."""
        if not self.hasPhoto():
            return

        zoom = max(0, self._zoom + step)
        if zoom != self._zoom:
            self._zoom = zoom
            if self._zoom > 0:
                factor = ZOOM_SCALE_FACTOR**step
                self.scale(factor, factor)
            else:
                self.resetView()
            self._update_grid()
            self._update_info_banner()

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel zoom."""
        if self.hasPhoto():
            delta = event.angleDelta().y()
            if delta:
                self.zoom(delta // abs(delta))

    def resizeEvent(self, event) -> None:
        """Handle window resize."""
        super().resizeEvent(event)
        if self.hasPhoto():
            self.resetView()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse movement for coordinate tracking and bbox editing."""
        if not (self.draw_bbox_mode and (self.bbox_dragging or self.bbox_resizing)):
            self.updateCoordinates(event.position().toPoint())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release for coordinate copying."""
        if event.button() == Qt.MouseButton.LeftButton and not self.draw_bbox_mode:
            release_pos = event.position().toPoint()
            delta = release_pos - self._mouse_pressed_pos

            # Simple click detection
            if abs(delta.x()) <= 3 and abs(delta.y()) <= 3 and self.hasPhoto():
                scene_pos = self.mapToScene(release_pos)
                pixmap = self._photo.pixmap()
                if not pixmap.isNull():
                    photo_rect = QRectF(pixmap.rect())
                    if photo_rect.contains(scene_pos):
                        self._copy_percentage_at_position(scene_pos)
        super().mouseReleaseEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press events."""
        if event.button() == Qt.MouseButton.RightButton:
            self.show_grid = not self.show_grid
            self._update_grid()
        elif event.button() == Qt.MouseButton.LeftButton and not self.draw_bbox_mode:
            self._mouse_pressed_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press events."""
        if event.key() == Qt.Key.Key_F:
            self.resetView()
            self._update_info_banner()
        else:
            super().keyPressEvent(event)

    def updateCoordinates(self, pos: QPoint | None = None) -> None:
        """Update coordinate display."""
        if self._photo.isUnderMouse():
            if pos is None:
                pos = self.mapFromGlobal(QCursor.pos())
            scene_pos = self.mapToScene(pos)
            point = QPoint(int(scene_pos.x()), int(scene_pos.y()))
        else:
            point = QPoint()
        self._on_coordinates_changed(point)

    def _on_coordinates_changed(self, point: QPoint) -> None:
        """Handle coordinate changes and update displays."""
        if not point.isNull():
            pixel_x = int(point.x())
            pixel_y = int(point.y())

            # Calculate coordinate information
            frame_x = self.frame_area.get("x", 0)
            frame_y = self.frame_area.get("y", 0)
            frame_width = self.frame_area.get("width", 1)
            frame_height = self.frame_area.get("height", 1)

            screen_x = frame_x + pixel_x
            screen_y = frame_y + pixel_y

            x_percent = max(0, min(100, (pixel_x / frame_width) * 100))
            y_percent = max(0, min(100, (pixel_y / frame_height) * 100))

            coord_section = f" MOUSE || Screen Coords: {screen_x:>5}, {screen_y:>4} | Frame Coords: {pixel_x:>4}, {pixel_y:>4} | Frame %: {x_percent:>7.4f}%, {y_percent:>7.4f}%"
        else:
            coord_section = (
                " MOUSE || Screen Coords: -----, ---- | Frame Coords: ----, ---- | Frame %: --.----%, --.----%"
            )

        self.frame_info_label.setText(coord_section)

        # Update other coordinate displays
        copied_section = self._get_copied_coordinates_display()
        self.copied_info_label.setText(copied_section)

        locate_section = self._get_locate_coordinates_display()
        self.locate_info_label.setText(locate_section)

    def _get_copied_coordinates_display(self) -> str:
        """Get copied coordinates display string."""
        try:
            parts = self._last_copied.replace(" ", "").split(",")
            if len(parts) == 2:
                copied_frame_x = int(parts[0])
                copied_frame_y = int(parts[1])

                frame_x = self.frame_area.get("x", 0)
                frame_y = self.frame_area.get("y", 0)
                frame_width = self.frame_area.get("width", 1)
                frame_height = self.frame_area.get("height", 1)

                copied_screen_x = frame_x + copied_frame_x
                copied_screen_y = frame_y + copied_frame_y

                copied_x_percent = max(0, min(100, (copied_frame_x / frame_width) * 100))
                copied_y_percent = max(0, min(100, (copied_frame_y / frame_height) * 100))

                return f"COPIED || Screen Coords: {copied_screen_x:>5}, {copied_screen_y:>4} | Frame Coords: {copied_frame_x:>4}, {copied_frame_y:>4} | Frame %: {copied_x_percent:>7.4f}%, {copied_y_percent:>7.4f}%"

        except Exception:
            pass

        return "COPIED || Screen Coords: -----, ---- | Frame Coords: ----, ---- | Frame %:  --.----%, --.----%"

    def _get_locate_coordinates_display(self) -> str:
        """Get locate coordinates display string."""
        if hasattr(self, "target_x") and hasattr(self, "target_y") and self.locate_state > 0:
            frame_x = self.frame_area.get("x", 0)
            frame_y = self.frame_area.get("y", 0)
            frame_width = self.frame_area.get("width", 1)
            frame_height = self.frame_area.get("height", 1)

            locate_screen_x = frame_x + int(self.target_x)
            locate_screen_y = frame_y + int(self.target_y)

            locate_x_percent = max(0, min(100, (self.target_x / frame_width) * 100))
            locate_y_percent = max(0, min(100, (self.target_y / frame_height) * 100))

            return f"LOCATE || Screen Coords: {locate_screen_x:>5}, {locate_screen_y:>4} | Frame Coords: {int(self.target_x):>4}, {int(self.target_y):>4} | Frame %: {locate_x_percent:>7.4f}%, {locate_y_percent:>7.4f}%"
        else:
            return "LOCATE || Screen Coords: -----, ---- | Frame Coords: ----, ---- | Frame %: --.----%, --.----%"

    def _update_footer_banner(self) -> None:
        """Update footer with instructions and status."""
        frame_size_section = f"Frame: {self.frame_area.get('x', 0):>4}, {self.frame_area.get('y', 0):>4} | Size: {self.frame_area.get('width', 0):>4}x{self.frame_area.get('height', 0):>4}"
        grid_zoom_section = f"Grid: {'ON ' if self.show_grid else 'OFF'} | Zoom: {self._zoom:>2}x"
        footer_text = f"Instructions: Mouse: Wheel=Zoom, Drag=Pan, Right=Grid, Left=Copy%, F=Fit                    {frame_size_section}                    {grid_zoom_section}"
        self.footer_banner.setText(footer_text)

    def _update_info_banner(self) -> None:
        """Update info banners."""
        self._on_coordinates_changed(QPoint())
        self._update_footer_banner()

    def _copy_percentage_at_position(self, scene_pos: QPointF) -> None:
        """Copy percentage coordinates at position."""
        try:
            import pyperclip

            frame_width = self.frame_area.get("width", 1)
            frame_height = self.frame_area.get("height", 1)

            x_percent = max(0, min(100, (scene_pos.x() / frame_width) * 100))
            y_percent = max(0, min(100, (scene_pos.y() / frame_height) * 100))

            percentage_text = f"{x_percent / 100:.6f}, {y_percent / 100:.6f}"
            pyperclip.copy(percentage_text)

            pixel_x = int(scene_pos.x())
            pixel_y = int(scene_pos.y())
            self._last_copied = f"{pixel_x:>4}, {pixel_y:>4}"
            self._update_info_banner()
        except Exception:
            pass

    def _update_grid(self) -> None:
        """Update grid overlay."""
        if self._grid_item:
            self._scene.removeItem(self._grid_item)
            self._grid_item = None

        if self.show_grid and self.hasPhoto():
            pixmap = self._photo.pixmap()
            if not pixmap.isNull():
                transform = self.transform()
                scale_factor = transform.m11()
                if scale_factor >= 0.5:
                    grid_item = self._create_pixel_grid(pixmap.width(), pixmap.height())
                    if grid_item:
                        self._grid_item = grid_item
                        self._scene.addItem(self._grid_item)

        self._update_footer_banner()

    def _create_pixel_grid(self, width: int, height: int) -> QGraphicsItemGroup:
        """Create pixel grid overlay."""
        grid_group = QGraphicsItemGroup()
        pen = QPen(QColor(0, 255, 255, 128))
        pen.setWidth(1)
        pen.setCosmetic(True)

        transform = self.transform()
        scale_factor = transform.m11()

        # Calculate grid step based on zoom
        if scale_factor >= 8.0:
            step = 1
        elif scale_factor >= 4.0:
            step = 2
        elif scale_factor >= 2.0:
            step = 5
        else:
            step = 10

        # Create grid lines
        for x in range(0, width + 1, step):
            line = QGraphicsLineItem(x, 0, x, height)
            line.setPen(pen)
            grid_group.addToGroup(line)

        for y in range(0, height + 1, step):
            line = QGraphicsLineItem(0, y, width, y)
            line.setPen(pen)
            grid_group.addToGroup(line)

        return grid_group

    # Simplified stubs for bbox and locate functionality
    def _on_draw_bbox_clicked(self) -> None:
        """Handle draw bbox button (simplified)."""
        pass

    def _on_locate_clicked(self) -> None:
        """Handle locate button (simplified)."""
        pass

    def _on_clear_clicked(self) -> None:
        """Handle clear button (simplified)."""
        pass

    def _update_locate_animation(self) -> None:
        """Update locate animation (simplified)."""
        pass
