"""Window detection utilities.

Extracted from tracker_enhanced-reference-only.py
"""

from __future__ import annotations
from typing import Dict, Optional


def find_target_window(target_process: str) -> Optional[Dict]:
    """Find the target window and its geometry. Returns info dict or None.

    NOTE: Logic copied verbatim from original monolithic file (except imports localized)
    to avoid changing behaviour.
    """
    try:  # Local imports so optional deps failure degrades gracefully
        import psutil  # type: ignore
        import win32gui  # type: ignore
        import win32process  # type: ignore
    except ImportError:
        return None

    target_pids = []  # Enumerate candidate PIDs first

    def enum_windows_callback(hwnd, _):  # Collect PIDs whose visible title contains WidgetInc
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

    from .refine import _refine_frame_borders_pyautogui  # local import to avoid circular

    for pid in target_pids:
        try:
            proc = psutil.Process(pid)
            if proc.is_running() and proc.name() == target_process:

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
                if not windows:
                    continue
                hwnd = windows[0]
                rect = win32gui.GetWindowRect(hwnd)
                client_rect = win32gui.GetClientRect(hwnd)
                client_left_top = win32gui.ClientToScreen(hwnd, (client_rect[0], client_rect[1]))
                client_right_bottom = win32gui.ClientToScreen(hwnd, (client_rect[2], client_rect[3]))
                client_x = client_left_top[0]
                client_y = client_left_top[1]
                client_w = client_right_bottom[0] - client_left_top[0]
                client_h = client_right_bottom[1] - client_left_top[1]
                title = win32gui.GetWindowText(hwnd)

                target_ratio = 3.0 / 2.0
                client_ratio = client_w / client_h if client_h else 1
                if client_ratio > target_ratio:  # fit height
                    frame_height = client_h
                    frame_width = int(frame_height * target_ratio)
                    px = client_x + (client_w - frame_width) // 2
                    py = client_y
                else:  # fit width
                    frame_width = client_w
                    frame_height = int(frame_width / target_ratio)
                    px = client_x
                    py = client_y + (client_h - frame_height) // 2

                frame_area = {"x": px, "y": py, "width": frame_width, "height": frame_height}
                refined_frame = _refine_frame_borders_pyautogui(frame_area)
                refinement_applied = False
                if refined_frame and refined_frame != frame_area:
                    frame_area = refined_frame
                    refinement_applied = True

                return {
                    "pid": pid,
                    "window_info": {
                        "hwnd": hwnd,
                        "title": title,
                        "window_rect": rect,
                        "client_left": client_x,
                        "client_top": client_y,
                        "client_width": client_w,
                        "client_height": client_h,
                    },
                    "frame_area": frame_area,
                    "refinement_applied": refinement_applied,
                }
        except Exception:
            continue
    return None
