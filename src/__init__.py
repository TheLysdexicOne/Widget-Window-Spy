"""
Widget Window Spy

A professional screenshot analysis tool that provides pixel-perfect coordinate tracking,
visualization, and bbox management for automation development.

Features:
- Real-time coordinate tracking across multiple coordinate systems
- Professional screenshot viewer with bbox editing capabilities
- Grid overlay and zoom functionality for precise alignment
- Clipboard integration for coordinate copying
- Freeze functionality for static coordinate capture
"""

__version__ = "1.0.0"
__author__ = "Widget Automation Tools"
__license__ = "MIT"

from .core import CoordinateSystem, MouseTracker
from .ui import TrackerWidget, ScreenshotViewer
from .utils import find_target_window

__all__ = ["CoordinateSystem", "MouseTracker", "TrackerWidget", "ScreenshotViewer", "find_target_window"]
