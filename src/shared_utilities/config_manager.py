"""Configuration manager for Widget Window Spy.

Handles loading and saving application settings and window geometry.
"""

from __future__ import annotations

import configparser
from pathlib import Path
from typing import Any
from PyQt6.QtCore import QRect


class ConfigManager:
    """Manages application configuration and window geometry persistence."""

    def __init__(self, config_path: str | Path | None = None):
        if config_path is None:
            # Default to config/tracker.cfg relative to project root
            project_root = Path(__file__).parent.parent.parent
            self.config_path = project_root / "config" / "tracker.cfg"
        else:
            self.config_path = Path(config_path)
        self.config = configparser.ConfigParser()
        self.load_config()

    def load_config(self) -> None:
        """Load configuration from file."""
        try:
            if self.config_path.exists():
                self.config.read(self.config_path, encoding="utf-8")
            else:
                # Create default config if file doesn't exist
                self._set_default_config()
                self.save_config()
        except Exception:
            # If config is corrupted, use defaults
            self._set_default_config()

    def save_config(self) -> None:
        """Save configuration to file."""
        try:
            # Ensure config directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_path, "w", encoding="utf-8") as f:
                self.config.write(f)
        except Exception:
            pass  # Fail silently if we can't save config

    def _set_default_config(self) -> None:
        """Set default configuration."""
        # Clear existing config
        self.config.clear()

        # Widget Inc section
        self.config.add_section("widget_inc")
        self.config.set("widget_inc", "target_process", "WidgetInc.exe")
        self.config.set("widget_inc", "default_copy_mode", "frame_coords")

        # System section
        self.config.add_section("system")

        # Tracker GUI section
        self.config.add_section("tracker_gui")
        self.config.set("tracker_gui", "x", "100")
        self.config.set("tracker_gui", "y", "100")
        self.config.set("tracker_gui", "width", "325")
        self.config.set("tracker_gui", "height", "500")

        # Screenshot GUI section
        self.config.add_section("screenshot_gui")
        self.config.set("screenshot_gui", "x", "400")
        self.config.set("screenshot_gui", "y", "100")
        self.config.set("screenshot_gui", "width", "1280")
        self.config.set("screenshot_gui", "height", "720")

    def get_window_geometry(self, window_name: str) -> QRect | None:
        """Get window geometry for the specified window."""
        try:
            if self.config.has_section(window_name):
                section = self.config[window_name]
                x = section.getint("x", 100)
                y = section.getint("y", 100)
                width = section.getint("width", 800)
                height = section.getint("height", 600)
                return QRect(x, y, width, height)
        except Exception:
            pass
        return None

    def save_window_geometry(self, window_name: str, geometry: QRect) -> None:
        """Save window geometry for the specified window."""
        try:
            if not self.config.has_section(window_name):
                self.config.add_section(window_name)

            self.config.set(window_name, "x", str(geometry.x()))
            self.config.set(window_name, "y", str(geometry.y()))
            self.config.set(window_name, "width", str(geometry.width()))
            self.config.set(window_name, "height", str(geometry.height()))
            self.save_config()
        except Exception:
            pass

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get a UI preference value."""
        try:
            if self.config.has_section("system"):
                return self.config.get("system", key, fallback=default)
        except Exception:
            pass
        return default

    def save_preference(self, key: str, value: Any) -> None:
        """Save a UI preference value."""
        try:
            if not self.config.has_section("system"):
                self.config.add_section("system")

            self.config.set("system", key, str(value))
            self.save_config()
        except Exception:
            pass

    def get_widget_inc_setting(self, key: str, default: str = "") -> str:
        """Get a widget_inc section setting."""
        try:
            return self.config.get("widget_inc", key, fallback=default)
        except Exception:
            return default

    def save_widget_inc_setting(self, key: str, value: str) -> None:
        """Save a widget_inc section setting."""
        try:
            if not self.config.has_section("widget_inc"):
                self.config.add_section("widget_inc")

            self.config.set("widget_inc", key, value)
            self.save_config()
        except Exception:
            pass


# Global config manager instance
_config_manager: ConfigManager | None = None


def get_config_manager() -> ConfigManager:
    """Get the global config manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
