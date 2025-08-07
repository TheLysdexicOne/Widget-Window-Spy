#!/usr/bin/env python3
"""
Core constants for Widget Window Spy application.
All configuration values and constants centralized here.
"""

# Application Configuration
APP_TITLE = "Widget Window Spy"
TARGET_PROCESS_DEFAULT = "WidgetInc.exe"
WINDOW_STAYS_ON_TOP = True

# Coordinate System Constants
PIXEL_ART_GRID_WIDTH = 192
PIXEL_ART_GRID_HEIGHT = 128
TARGET_ASPECT_RATIO = 3.0 / 2.0
TARGET_FRAME_WIDTH = 2054

# UI Constants
FONT_FAMILY = "'Consolas', 'Courier New', monospace"
FONT_SIZE_COORDINATES = 9
FONT_SIZE_HEADERS = 12
FONT_SIZE_TITLE = 14

# Colors (Professional Dark Theme)
COLOR_BACKGROUND_PRIMARY = "#1e1e1e"
COLOR_BACKGROUND_SECONDARY = "#2d2d2d"
COLOR_BACKGROUND_TERTIARY = "#3d3d3d"
COLOR_TEXT_PRIMARY = "#ffffff"
COLOR_TEXT_SECONDARY = "#cccccc"
COLOR_TEXT_ACCENT = "#00ff88"
COLOR_ACCENT_GREEN = "#4caf50"
COLOR_ACCENT_BLUE = "#1976d2"
COLOR_ACCENT_YELLOW = "#ffa500"
COLOR_ACCENT_RED = "#d32f2f"
COLOR_BORDER = "#555555"
COLOR_GRID = "#00ffff"

# Bbox System Colors
COLOR_BBOX_MAIN = "#ffff00"  # Yellow
COLOR_BBOX_HANDLES = "#ff0000"  # Red for handles

# Timing Constants (milliseconds)
TIMER_MONITOR_INTERVAL = 2000
TIMER_MOUSE_TRACKING_INTERVAL = 100
TIMER_LOCATE_ANIMATION_INTERVAL = 100
TIMER_FEEDBACK_DURATION = 2000

# Screenshot and Grid Constants
GRID_STEP_ZOOM_8 = 1
GRID_STEP_ZOOM_4 = 2
GRID_STEP_ZOOM_2 = 5
GRID_STEP_ZOOM_1 = 10
ZOOM_SCALE_FACTOR = 1.25
OVERPAN_PIXELS = 75

# Multi-monitor bounds for safety
MONITOR_BOUNDS_LEFT = -3840
MONITOR_BOUNDS_RIGHT = 7680

# Pixel checking and refinement
REFINEMENT_TOLERANCE = 10  # pixels
HANDLE_MIN_SIZE = 8
HANDLE_SCALE_FACTOR = 16
CORNER_DETECTION_THRESHOLD = 12

# Animation Constants
LOCATE_ANIMATION_MAX_RADIUS = 50
LOCATE_ANIMATION_STEPS = 20
BBOX_MIN_SIZE = 10
INITIAL_BBOX_SIZE = 100

# Table Dimensions
TABLE_HEIGHT_COORDS = 90
TABLE_HEIGHT_MOUSE = 140
WIDGET_MIN_WIDTH = 325
WIDGET_MIN_HEIGHT = 100
WIDGET_MAX_WIDTH = 325
WIDGET_MAX_HEIGHT = 16777215

# Click Detection
CLICK_TOLERANCE_PIXELS = 3

# Coordinate Format Strings (Exact spacing required)
COORD_FORMAT_MOUSE = "MOUSE || Screen Coords: {screen_x:>5}, {screen_y:>4} | Frame Coords: {frame_x:>4}, {frame_y:>4} | Frame %: {x_percent:>7.4f}%, {y_percent:>7.4f}%"
COORD_FORMAT_COPIED = "COPIED || Screen Coords: {screen_x:>5}, {screen_y:>4} | Frame Coords: {frame_x:>4}, {frame_y:>4} | Frame %: {x_percent:>7.4f}%, {y_percent:>7.4f}%"
COORD_FORMAT_LOCATE = "LOCATE || Screen Coords: {screen_x:>5}, {screen_y:>4} | Frame Coords: {frame_x:>4}, {frame_y:>4} | Frame %: {x_percent:>7.4f}%, {y_percent:>7.4f}%"
COORD_FORMAT_BBOX = "COPIED || BBOX: Frame({x1:>4},{y1:>4},{x2:>4},{y2:>4}) | Screen({screen_x1:>4},{screen_y1:>4},{screen_x2:>4},{screen_y2:>4})"
COORD_FORMAT_EMPTY = "----, ----"
COORD_FORMAT_OUTSIDE = "Outside"
COORD_FORMAT_NA = "N/A"
COORD_FORMAT_ERROR = "Error"

# Logging Configuration
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
