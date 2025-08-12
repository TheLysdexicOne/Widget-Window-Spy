"""Configuration manager for Widget Window Spy.

Handles loading and saving application settings and window geometry.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any
from PyQt6.QtCore import QRect


class ConfigManager:
    """Manages application configuration and window geometry persistence."""

    def __init__(self, config_path: str | Path | None = None):
        if config_path is None:
            # Default to config/tracker.config relative to project root
            project_root = Path(__file__).parent.parent.parent
            self.config_path = project_root / "config" / "tracker.config"
        else:
            self.config_path = Path(config_path)
        self.config_data: Dict[str, Any] = {}
        self.load_config()

    def load_config(self) -> None:
        """Load configuration from file."""
        try:
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.config_data = json.load(f)
            else:
                # Create default config if file doesn't exist
                self.config_data = self._get_default_config()
                self.save_config()
        except Exception:
            # If config is corrupted, use defaults
            self.config_data = self._get_default_config()

    def save_config(self) -> None:
        """Save configuration to file."""
        try:
            # Ensure config directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=4)
        except Exception:
            pass  # Fail silently if we can't save config

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "window_geometry": {
                "main_window": {"x": 100, "y": 100, "width": 325, "height": 500},
                "screenshot_viewer": {"x": 400, "y": 100, "width": 1280, "height": 720},
            },
            "ui_preferences": {"grid_enabled": False, "copy_mode": "Frame Coords", "zoom_level": 0},
        }

    def get_window_geometry(self, window_name: str) -> QRect | None:
        """Get window geometry for the specified window."""
        try:
            geom = self.config_data.get("window_geometry", {}).get(window_name, {})
            if all(key in geom for key in ["x", "y", "width", "height"]):
                return QRect(geom["x"], geom["y"], geom["width"], geom["height"])
        except Exception:
            pass
        return None

    def save_window_geometry(self, window_name: str, geometry: QRect) -> None:
        """Save window geometry for the specified window."""
        try:
            if "window_geometry" not in self.config_data:
                self.config_data["window_geometry"] = {}

            self.config_data["window_geometry"][window_name] = {
                "x": geometry.x(),
                "y": geometry.y(),
                "width": geometry.width(),
                "height": geometry.height(),
            }
            self.save_config()
        except Exception:
            pass

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get a UI preference value."""
        return self.config_data.get("ui_preferences", {}).get(key, default)

    def save_preference(self, key: str, value: Any) -> None:
        """Save a UI preference value."""
        try:
            if "ui_preferences" not in self.config_data:
                self.config_data["ui_preferences"] = {}

            self.config_data["ui_preferences"][key] = value
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
