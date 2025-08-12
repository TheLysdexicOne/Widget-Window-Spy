from __future__ import annotations
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor, QPen, QBrush
from PyQt6.QtWidgets import QGraphicsRectItem


class SquareTool:
    """Grid-snapped square selection tool.

    - Spawns at configurable default size (DEFAULT_SIZE in pixels)
    - Valid sizes: 16px, 32px, 48px, 64px, 80px, 96px, ... up to 512px
    - Linear progression in 16px increments for precise control
    - Button-controlled resize with size snapping
    - Raw mouse movement (no smoothing)
    - Always grid-aligned positioning
    """

    # Configuration constants (in pixels)
    DEFAULT_SIZE = 64  # Starting size in pixels
    MIN_SIZE = 16     # Minimum size in pixels
    MAX_SIZE = 512    # Maximum size in pixels
    SIZE_STEP = 16    # Increment step in pixels
    
    # Generate valid sizes as multiples of 16 from 16 to 512
    VALID_SIZES = list(range(MIN_SIZE, MAX_SIZE + SIZE_STEP, SIZE_STEP))

    def __init__(self, scene, frame_area: dict, copy_mode_manager):
        self.scene = scene
        self.frame_area = frame_area
        self.copy_mode_manager = copy_mode_manager
        self.rect_item: QGraphicsRectItem | None = None
        self.grid_lines: list = []  # Internal grid lines
        self.dragging = False
        self.resizing = False  # Required by screenshot_gui
        self.resize_direction: str | None = None
        self._current_size: int = self.DEFAULT_SIZE

    # ------------------------------------------------------------------
    # Grid snapping utilities
    # ------------------------------------------------------------------
    def _snap_to_grid(self, value: float) -> float:
        """Snap coordinate to single pixel grid."""
        return round(value)  # Always snap to 1px intervals

    def _get_closest_valid_size(self, target_size: float) -> int:
        """Get closest valid square size (in pixels)."""
        # Round to nearest multiple of SIZE_STEP, then clamp to valid range
        rounded_size = round(target_size / self.SIZE_STEP) * self.SIZE_STEP
        clamped_size = max(self.MIN_SIZE, min(self.MAX_SIZE, rounded_size))
        return int(clamped_size)

    def _size_in_pixels(self, size_pixels: int) -> int:
        """Size is already in pixels - no conversion needed."""
        return size_pixels

    def _create_internal_grid(self):
        """Create 16x16 grid lines inside the square."""
        self._clear_grid()
        if not self.rect_item:
            return

        rect = self.rect_item.rect()
        size = rect.width()
        grid_interval = size / 16  # Always 16x16 grid

        # Create grid lines
        pen = QPen(QColor(0, 255, 255, 80))  # Semi-transparent cyan
        pen.setWidth(1)
        pen.setCosmetic(True)

        # Vertical lines
        for i in range(1, 16):  # Skip borders (0 and 16)
            x = rect.left() + (i * grid_interval)
            line = self.scene.addLine(x, rect.top(), x, rect.bottom(), pen)
            self.grid_lines.append(line)

        # Horizontal lines
        for i in range(1, 16):  # Skip borders (0 and 16)
            y = rect.top() + (i * grid_interval)
            line = self.scene.addLine(rect.left(), y, rect.right(), y, pen)
            self.grid_lines.append(line)

    def _clear_grid(self):
        """Remove all internal grid lines."""
        for line in self.grid_lines:
            try:
                self.scene.removeItem(line)
            except Exception:
                pass
        self.grid_lines.clear()

    # ------------------------------------------------------------------
    # Lifecycle / creation
    # ------------------------------------------------------------------
    def ensure_created(self, pixmap_width: int, pixmap_height: int):
        if self.rect_item is None:
            side = self.DEFAULT_SIZE  # Use configurable default
            self._current_size = side
            left = (pixmap_width - side) / 2
            top = (pixmap_height - side) / 2
            self.rect_item = QGraphicsRectItem(left, top, side, side)
            pen = QPen(QColor(0, 200, 255))
            pen.setWidth(2)
            pen.setCosmetic(True)
            self.rect_item.setPen(pen)
            self.rect_item.setBrush(QBrush())
            self.scene.addItem(self.rect_item)
            self._create_internal_grid()
            self.update_clipboard()

    def create_initial(self, pixmap_width: int, pixmap_height: int, scale: float):
        """API expected by screenshot_gui - spawn at default size."""
        if self.rect_item is None:
            side = self.DEFAULT_SIZE
            self._current_size = side
            left = (pixmap_width - side) / 2
            top = (pixmap_height - side) / 2
            self.rect_item = QGraphicsRectItem(left, top, side, side)
            pen = QPen(QColor(0, 200, 255))
            pen.setWidth(2)
            pen.setCosmetic(True)
            self.rect_item.setPen(pen)
            self.rect_item.setBrush(QBrush())
            self.scene.addItem(self.rect_item)
            self._create_internal_grid()
            self.update_clipboard()

    def clear(self):
        """API expected by screenshot_gui - remove square."""
        if self.rect_item is not None:
            try:
                self.scene.removeItem(self.rect_item)
            except Exception:
                pass
            self.rect_item = None
        self._clear_grid()
        self.dragging = False
        self.resizing = False
        self.resize_direction = None
        self._current_size = self.DEFAULT_SIZE

    # ------------------------------------------------------------------
    # Interaction state
    # ------------------------------------------------------------------
    def detect_resize_direction(self, scene_pos: QPointF, scale: float):
        """No corner resize - use +/- buttons for size control."""
        return None

    def begin_drag(self, scene_pos: QPointF | None = None):
        """Start dragging from current position."""
        if not self.rect_item:
            return
        self.dragging = True

    def begin_resize(self, direction: str):
        """No resize by dragging - maintained for API compatibility."""
        pass

    # ------------------------------------------------------------------
    # Size control methods
    # ------------------------------------------------------------------
    def size_up(self):
        """Increase square size to next valid size."""
        current_index = self.VALID_SIZES.index(self._current_size)
        if current_index < len(self.VALID_SIZES) - 1:
            new_size = self.VALID_SIZES[current_index + 1]
            self._resize_to_size(new_size)

    def size_down(self):
        """Decrease square size to previous valid size."""
        current_index = self.VALID_SIZES.index(self._current_size)
        if current_index > 0:
            new_size = self.VALID_SIZES[current_index - 1]
            self._resize_to_size(new_size)

    def get_size_info(self) -> dict:
        """Get current size information for UI display."""
        current_index = self.VALID_SIZES.index(self._current_size)
        return {
            "current_size": self._current_size,  # In pixels
            "current_size_pixels": self._current_size,  # Same as above
            "current_index": current_index,
            "can_size_up": current_index < len(self.VALID_SIZES) - 1,
            "can_size_down": current_index > 0,
            "grid_interval": self._current_size // 16,  # px per grid cell
            "total_cells": 16 * 16,  # Always 16x16 grid
        }

    # ------------------------------------------------------------------
    # Motion / geometry
    # ------------------------------------------------------------------
    def apply_motion(self, dx: float, dy: float, scale: float, snap_rect_callback=None, show_grid=False):
        """Apply raw mouse movement - drag only, no resize."""
        if self.rect_item is None or not self.dragging:
            return

        # Raw 1:1 mouse movement - no grid snapping during drag
        current_rect = self.rect_item.rect()
        new_left = current_rect.left() + dx
        new_top = current_rect.top() + dy
        self.rect_item.setRect(new_left, new_top, current_rect.width(), current_rect.height())
        # Update grid position
        self._create_internal_grid()

    def _resize_to_size(self, new_size: int):
        """Resize square to specific size, maintaining center position."""
        # Always update logical size, even when not visible
        self._current_size = new_size
        
        # Only update visual representation if square is currently visible
        if self.rect_item:
            current_rect = self.rect_item.rect()
            center_x = current_rect.center().x()
            center_y = current_rect.center().y()

            half_size = new_size / 2
            new_left = center_x - half_size
            new_top = center_y - half_size

            self.rect_item.setRect(new_left, new_top, new_size, new_size)
            self._create_internal_grid()
            self.update_clipboard()    # ------------------------------------------------------------------
    # Finish / clipboard
    # ------------------------------------------------------------------
    def finish_interaction(self):
        """Complete drag operation with grid snapping."""
        if self.dragging and self.rect_item:
            # Snap to grid on release
            current_rect = self.rect_item.rect()
            snapped_left = self._snap_to_grid(current_rect.left())
            snapped_top = self._snap_to_grid(current_rect.top())
            self.rect_item.setRect(snapped_left, snapped_top, current_rect.width(), current_rect.height())
            self._create_internal_grid()

        self.dragging = False
        self.resizing = False
        self.resize_direction = None
        self.update_clipboard()

    def update_clipboard(self):
        """Copy current square coordinates to clipboard."""
        if self.rect_item is None:
            return
        r = self.rect_item.rect()
        self.copy_mode_manager.copy_rect((r.left(), r.top(), r.right(), r.bottom()), self.frame_area)

    # ------------------------------------------------------------------
    # Convenience accessor
    # ------------------------------------------------------------------
    def current_rect(self) -> tuple[float, float, float, float] | None:
        """Get current square bounds as (left, top, right, bottom)."""
        if not self.rect_item:
            return None
        r = self.rect_item.rect()
        return r.left(), r.top(), r.right(), r.bottom()
