#!/usr/bin/env python3
"""
Window detection utilities for Widget Window Spy.
Handles finding and analyzing target application windows.
"""

from typing import Dict, List, Optional

try:
    import psutil
    import win32gui
    import win32process

    WINDOWS_API_AVAILABLE = True
except ImportError:
    WINDOWS_API_AVAILABLE = False

from core.coordinates import CoordinateSystem
from core.constants import TARGET_FRAME_WIDTH, REFINEMENT_TOLERANCE, MONITOR_BOUNDS_LEFT, MONITOR_BOUNDS_RIGHT


def find_target_window(target_process: str) -> Optional[Dict]:
    """
    Find the target window and its geometry.
    Returns comprehensive window information or None if not found.
    """
    if not WINDOWS_API_AVAILABLE:
        return None

    # Step 1: Find target process IDs by window title
    target_pids = _find_target_pids(target_process)
    if not target_pids:
        return None

    # Step 2: Find first valid process and its window
    for pid in target_pids:
        window_info = _get_window_info_for_pid(pid, target_process)
        if window_info:
            return window_info

    return None


def _find_target_pids(target_process: str) -> List[int]:
    """Find process IDs for windows with WidgetInc in title."""
    if not WINDOWS_API_AVAILABLE:
        return []

    target_pids = []

    def enum_windows_callback(hwnd, _):
        try:
            title = win32gui.GetWindowText(hwnd)
            if "WidgetInc" in title and win32gui.IsWindowVisible(hwnd):
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid not in target_pids:
                    target_pids.append(pid)
        except Exception:
            pass
        return True

    win32gui.EnumWindows(enum_windows_callback, None)
    return target_pids


def _get_window_info_for_pid(pid: int, target_process: str) -> Optional[Dict]:
    """Get window information for a specific process ID."""
    if not WINDOWS_API_AVAILABLE:
        return None

    try:
        # Verify process is running and matches target
        proc = psutil.Process(pid)
        if not proc.is_running() or proc.name() != target_process:
            return None

        # Find window for this PID
        hwnd = _find_window_for_pid(pid)
        if not hwnd:
            return None

        # Get window geometry
        window_rect = win32gui.GetWindowRect(hwnd)
        client_rect = win32gui.GetClientRect(hwnd)

        # Convert client area to screen coordinates
        client_coords = _get_client_screen_coords(hwnd, client_rect)
        if not client_coords:
            return None

        client_x, client_y, client_w, client_h = client_coords
        title = win32gui.GetWindowText(hwnd)

        # Calculate frame area
        coord_system = CoordinateSystem()
        frame_area = coord_system.calculate_frame_area(client_x, client_y, client_w, client_h)

        # Apply refinement if needed
        refined_frame = _refine_frame_borders(frame_area)
        refinement_applied = refined_frame != frame_area
        if refinement_applied:
            frame_area = refined_frame

        return {
            "pid": pid,
            "window_info": {
                "hwnd": hwnd,
                "title": title,
                "window_rect": window_rect,
                "client_left": client_x,
                "client_top": client_y,
                "client_width": client_w,
                "client_height": client_h,
            },
            "frame_area": frame_area,
            "refinement_applied": refinement_applied,
        }

    except Exception:
        return None


def _find_window_for_pid(pid: int) -> Optional[int]:
    """Find the main window handle for a process ID."""
    try:
        import win32gui
        import win32process
    except ImportError:
        return None

    def enum_windows_proc(hwnd, windows):
        try:
            _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
            if window_pid == pid and win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if "WidgetInc" in title:
                    windows.append(hwnd)
        except Exception:
            pass
        return True

    windows = []
    win32gui.EnumWindows(enum_windows_proc, windows)
    return windows[0] if windows else None


def _get_client_screen_coords(hwnd: int, client_rect: tuple) -> Optional[tuple]:
    """Convert client rectangle to screen coordinates."""
    try:
        import win32gui
    except ImportError:
        return None

    try:
        client_left_top = win32gui.ClientToScreen(hwnd, (client_rect[0], client_rect[1]))
        client_right_bottom = win32gui.ClientToScreen(hwnd, (client_rect[2], client_rect[3]))

        client_x = client_left_top[0]
        client_y = client_left_top[1]
        client_w = client_right_bottom[0] - client_left_top[0]
        client_h = client_right_bottom[1] - client_left_top[1]

        return client_x, client_y, client_w, client_h
    except Exception:
        return None


def _refine_frame_borders(frame_area: Dict) -> Dict:
    """
    Refine frame borders using pixel analysis.
    Attempts to achieve exactly TARGET_FRAME_WIDTH pixel width.
    """
    if not frame_area:
        return frame_area

    x = frame_area.get("x", 0)
    y = frame_area.get("y", 0)
    width = frame_area.get("width", 0)
    height = frame_area.get("height", 0)

    # Only refine if width is close to target
    if abs(width - TARGET_FRAME_WIDTH) > REFINEMENT_TOLERANCE:
        return frame_area

    try:
        width_diff = TARGET_FRAME_WIDTH - width

        if width_diff == 0:
            return frame_area

        # Special case for 2053->2054: expand right to preserve X position
        if width == 2053 and TARGET_FRAME_WIDTH == 2054:
            return {"x": x, "y": y, "width": TARGET_FRAME_WIDTH, "height": height}

        # Try various adjustments
        adjustments = _get_border_adjustments(width_diff)

        for left_adj, right_adj in adjustments:
            new_x = x + left_adj
            new_width = width - left_adj + right_adj

            if new_width == TARGET_FRAME_WIDTH and _validate_border_adjustment(new_x, new_width, y):
                return {"x": new_x, "y": y, "width": new_width, "height": height}

        return frame_area

    except Exception:
        return frame_area


def _get_border_adjustments(width_diff: int) -> List[tuple]:
    """Get list of border adjustment strategies."""
    adjustments = []

    if abs(width_diff) <= 4:
        if width_diff > 0:  # Need to increase width
            adjustments = [
                (0, width_diff),  # Expand right only (preserves X)
                (-width_diff, 0),  # Expand left only
                (-width_diff // 2, width_diff // 2 + width_diff % 2),  # Expand both
            ]
        else:  # Need to decrease width
            width_diff = abs(width_diff)
            adjustments = [
                (0, -width_diff),  # Contract right only (preserves X)
                (width_diff, 0),  # Contract left only
                (width_diff // 2, -(width_diff // 2 + width_diff % 2)),  # Contract both
            ]

    return adjustments


def _validate_border_adjustment(new_x: int, new_width: int, y: int) -> bool:
    """Validate border adjustment using pixel sampling."""
    try:
        import pyautogui

        validation_y = y + 50  # Use middle-ish Y coordinate
        left_x = new_x - 1
        right_x = new_x + new_width

        # Check if coordinates are within safe multi-monitor bounds
        if not (
            MONITOR_BOUNDS_LEFT <= left_x < MONITOR_BOUNDS_RIGHT
            and MONITOR_BOUNDS_LEFT <= right_x < MONITOR_BOUNDS_RIGHT
        ):
            return False

        # Sample pixels to validate borders
        left_pixel = pyautogui.pixel(left_x, validation_y)
        right_pixel = pyautogui.pixel(right_x, validation_y)

        # Simple heuristic: borders should be different colors
        return left_pixel != right_pixel

    except Exception:
        return False
