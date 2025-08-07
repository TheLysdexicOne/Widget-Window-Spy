# Widget Automation Tool: AI Coding Agent Instructions

## Essential Architecture Knowledge

### Core Principles

- **KISS** - "Keep It Simple Stupid": Manual selection beats unreliable detection
- **DRY** - "Don't Repeat Yourself": Extract common automation patterns to shared utilities
- **Workflow** - "Make it Work, Make it Right, Make it Fast": Focus on function before form
- **Clean Functional Design** - Don't go overboard on looks until application functions correctly
- **Virtual Environment is Absolute Must** - Everything needed is in the virtual environment, no global installs

### Core Components & Data Flow

- **CacheManager (`utility/cache_manager.py`)** - Centralized window detection & caching. Get via `get_cache_manager()` singleton
- **AutomationController (`automation/automation_controller.py`)** - Orchestrates threading & frame automator lifecycle
- **MainWindow (`main.py`)** - PyQt6 overlay that snaps to WidgetInc window, creates frame buttons dynamically from database
- **Frame Automators (`automation/frame_automators/tier_*/`)** - Individual automation scripts inheriting from `BaseAutomator`

### Critical Coordinate System

- All coordinates are **frame-relative** (0,0 = top-left of game area), not screen coordinates
- Use `frame_to_screen_coords(x, y)` for clicks: `automation_engine.frame_click(frame_x, frame_y)`
- Screenshots: `ImageGrab.grab(...all_screens=True)` for multi-monitor support
- Grid system: 192x128 pixel art units, use `PIXEL_ART_GRID_WIDTH/HEIGHT` constants

### Database & Caching Pattern

- Frames database: `config/database/frames_database.json` → `frames.cache` (screen coords)
- CacheManager auto-generates cache from database, validates every 5s with database file watching
- **Three coordinate systems**: Grid (user-friendly) → Screen (absolute) → Frame (relative)
- **Database validation is necessary** - User edits JSON, corruption breaks coordinate translation
- **Never edit frames.cache directly** - it's auto-generated from frames_database.json

## Essential Architecture Knowledge

### Core Purpose

A professional screenshot analysis tool that provides pixel-perfect coordinate tracking, visualization, and bbox management for automation development. Built with PyQt6 for cross-platform compatibility.

### Design Philosophy

- **Precision First** - Monospace fonts, grid snapping, exact coordinate alignment
- **Professional UX** - Handle-based bbox editing similar to professional image editors
- **Real-time Feedback** - Live coordinate display across multiple coordinate systems
- **Non-destructive** - All operations preserve original screenshot data

## Core Components & Data Flow

### Main Classes

- **`MouseTracker`** - Global mouse position monitoring with coordinate system conversion
- **`ScreenshotViewer`** - Main PyQt6 graphics view with professional bbox editing capabilities
- **`TrackerWidget`** - Control panel with screenshot capture and mouse coordinate tables

### Critical Coordinate Systems

```python
# Three coordinate systems with automatic conversion:
screen_coords = (x, y)           # Absolute monitor coordinates
frame_coords = (x, y)            # Relative to captured frame (0,0 = top-left)
frame_percent = (x%, y%)         # Percentage within frame (0.0-1.0 or 0-100)

# Automatic detection based on values:
# - 0.0-1.0: Decimal percentages
# - 0-100: Integer percentages
# - >=1000: Screen coordinates
# - <1000: Frame coordinates
```

### Data Flow Architecture

```
Window Detection → Screenshot Capture → Coordinate Tracking → Visualization
     ↓                    ↓                    ↓               ↓
find_target_window() → PIL.Image → MouseTracker → ScreenshotViewer
                                        ↓               ↓
                               Coordinate Tables → Three-Line Header
```

## Development Patterns & Standards

### Font Hierarchy (Strictly Enforced)

```python
font_family = "'Consolas', 'Courier New', monospace"
# This exact order ensures consistent monospace rendering across platforms
```

### Coordinate Display Format (Exact Spacing Required)

```python
# All coordinate displays must use this exact formatting:
f"MOUSE || Screen Coords: {screen_x:>5}, {screen_y:>4} | Frame Coords: {frame_x:>4}, {frame_y:>4} | Frame %: {x_percent:>7.4f}%, {y_percent:>7.4f}%"
f"COPIED || Screen Coords: {screen_x:>5}, {screen_y:>4} | Frame Coords: {frame_x:>4}, {frame_y:>4} | Frame %: {x_percent:>7.4f}%, {y_percent:>7.4f}%"
f"LOCATE || Screen Coords: {screen_x:>5}, {screen_y:>4} | Frame Coords: {frame_x:>4}, {frame_y:>4} | Frame %: {x_percent:>7.4f}%, {y_percent:>7.4f}%"
```

### Three-Line Header System (Fixed Layout)

```
Line 1: MOUSE coordinates                              <stretch>  [Draw BBOX]
Line 2: COPIED coordinates                             <stretch>  LOCATE: [input]
Line 3: LOCATE coordinates                             <stretch>  [LOCATE] [CLEAR]
Footer: Instructions <stretch> Frame: x,y | Size: WxH <stretch> Grid: ON/OFF | Zoom: Nx
```

### Professional Bbox System Requirements

#### Handle-Based Editing (Like Photoshop/GIMP)

```python
# Edge handles - entire edges are clickable for resizing:
handle_types = {
    'n': 'North edge - vertical resize',
    's': 'South edge - vertical resize',
    'w': 'West edge - horizontal resize',
    'e': 'East edge - horizontal resize',
    'nw': 'Northwest corner - diagonal resize',
    'ne': 'Northeast corner - diagonal resize',
    'sw': 'Southwest corner - diagonal resize',
    'se': 'Southeast corner - diagonal resize'
}

# Center drag for moving entire bbox
# Grid snapping for precision alignment
```

#### Cursor Management (Professional Standards)

```python
resize_cursors = {
    'n': Qt.CursorShape.SizeVerCursor,     # ↕
    's': Qt.CursorShape.SizeVerCursor,     # ↕
    'w': Qt.CursorShape.SizeHorCursor,     # ↔
    'e': Qt.CursorShape.SizeHorCursor,     # ↔
    'nw': Qt.CursorShape.SizeFDiagCursor,  # ⤡
    'ne': Qt.CursorShape.SizeBDiagCursor,  # ⤢
    'sw': Qt.CursorShape.SizeBDiagCursor,  # ⤢
    'se': Qt.CursorShape.SizeFDiagCursor   # ⤡
}
```

## Critical Implementation Details

### Grid Snapping System

```python
def _snap_to_grid(self, value: float) -> float:
    """Snap coordinate to grid if grid is visible."""
    if not self.show_grid:
        return value
    # Grid spacing based on zoom level for pixel-perfect alignment
    grid_size = max(1, 10 // max(1, self._zoom))
    return round(value / grid_size) * grid_size
```

### Mouse Event State Management

```python
# Three distinct states for mouse interactions:
self.bbox_dragging = False      # Moving entire bbox
self.bbox_resizing = False      # Resizing via handles
self.bbox_resize_direction = None  # Which handle: 'n', 'se', etc.

# Pan/zoom only when NOT manipulating bbox
if not (self.draw_bbox_mode and (self.bbox_dragging or self.bbox_resizing)):
    # Allow normal view interactions
```

### Coordinate Input Parsing (Regex-Based)

```python
# Single input box handles all coordinate formats:
input_patterns = {
    r'^\s*(\d+(?:\.\d+)?)\s*[,\s]\s*(\d+(?:\.\d+)?)\s*$': 'point',
    r'^\s*(\d+(?:\.\d+)?)\s*[,\s]\s*(\d+(?:\.\d+)?)\s*[,\s]\s*(\d+(?:\.\d+)?)\s*[,\s]\s*(\d+(?:\.\d+)?)\s*$': 'bbox'
}
```

## Error Handling Philosophy

### Smart Fail-Fast for Graphics Operations

```python
# Good - let PyQt6 fail on invalid operations:
scene_pos = self.mapToScene(event.position().toPoint())
self.bbox_rect_item.setRect(new_rect)

# Bad - don't mask graphics system errors:
try:
    scene_pos = self.mapToScene(event.position().toPoint())
except:
    scene_pos = QPointF(0, 0)  # This masks real coordinate issues
```

### Required Error Handling Cases

```python
# File operations and external dependencies:
try:
    import psutil, win32gui, win32process
except ImportError as e:
    # Graceful degradation for window detection
    return None

# PIL/Screenshot operations:
try:
    screenshot = ImageGrab.grab(bbox=bbox, all_screens=True)
except Exception as e:
    # Screenshot can fail on permission/display issues
    self.status_callback(f"Screenshot failed: {e}")
```

## PyQt6 Specific Patterns

### Graphics Scene Management

```python
# Always use QGraphicsScene for overlays:
self._scene = QGraphicsScene(self)
self._photo = QGraphicsPixmapItem()
self.setScene(self._scene)

# Proper item lifecycle:
if self.bbox_rect_item:
    self._scene.removeItem(self.bbox_rect_item)
    self.bbox_rect_item = None
```

### Window Setup (Professional Overlay)

```python
# Standard window flags for screenshot viewer:
flags = Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint
self.window_widget.setWindowFlags(flags)

# Professional dark theme (minimal CSS):
stylesheet = """
    QWidget { background-color: #1e1e1e; color: #ffffff; }
    QLabel { font-family: 'Fira Code', 'Consolas', 'Courier New', monospace; }
"""
```

### Thread Safety (Mouse Tracking)

```python
# Use QTimer for safe GUI updates from background threads:
self.update_timer = QTimer()
self.update_timer.timeout.connect(self._update_mouse_position)
self.update_timer.start(16)  # ~60 FPS for smooth tracking
```

## File Organization Standards

```
tracker_enhanced.py              # Main standalone application
├── MouseTracker                 # Background mouse position monitoring
├── ScreenshotViewer             # Main graphics view with bbox editing
├── TrackerWidget               # Control panel and coordinate tables
└── Utility Functions           # Window detection, coordinate conversion
```

## Testing & Validation Patterns

### Coordinate System Validation

```python
# Always test coordinate round-trip accuracy:
frame_x, frame_y = 100, 200
screen_x, screen_y = frame_to_screen_coords(frame_x, frame_y)
back_frame_x, back_frame_y = screen_to_frame_coords(screen_x, screen_y)
assert (frame_x, frame_y) == (back_frame_x, back_frame_y)
```

### Handle Detection Testing

```python
# Verify handle detection at various zoom levels:
for zoom in [1, 2, 5, 10]:
    self._zoom = zoom
    handle_size = max(8, 16 // zoom)  # Minimum visible size
    # Test click detection accuracy
```

Use `semantic_search` to find coordinate conversion patterns, bbox manipulation examples, or PyQt6 graphics scene usage in the codebase.
