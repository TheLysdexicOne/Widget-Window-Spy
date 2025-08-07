"""
Widget Window Spy - Core Components

Core functionality for the Widget Window Spy application including
coordinate systems, mouse tracking, and configuration constants.
"""

from .coordinates import CoordinateSystem
from .mouse_tracker import MouseTracker

__all__ = [
    "CoordinateSystem",
    "MouseTracker",
]
