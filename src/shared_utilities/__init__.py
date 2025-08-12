"""Shared utilities package."""

from .config_manager import get_config_manager
from .coordinates import *
from .mouse_tracker import MouseTracker
from .window_detection import find_target_window
from .refine import *

__all__ = ["get_config_manager", "MouseTracker", "find_target_window"]
