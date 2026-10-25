"""Settings and saved state.

Settings come from `config.example.json`, overlaid by a git-ignored `config.local.json` next to
it. Saved state (card order, hidden cards, theme, window layouts, local tasks) lives under
%LOCALAPPDATA%, never in the repo, so a clone carries no personal data.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "state") / "nicegui-windows-console"


def _merge(base: dict, override: dict) -> dict:
    """Deep-merge dicts; lists and scalars in `override` replace those in `base`."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(app_dir: Path = APP_DIR) -> dict[str, Any]:
    config = json.loads((app_dir / "config.example.json").read_text(encoding="utf-8"))
    local = app_dir / "config.local.json"
    if local.exists():
        config = _merge(config, json.loads(local.read_text(encoding="utf-8")))
    return config


def expand(path: str | Path) -> Path:
    """Expand ~ and %VARS%, and resolve relative paths against the app folder."""
    expanded = Path(os.path.expandvars(os.path.expanduser(str(path))))
    return expanded if expanded.is_absolute() else APP_DIR / expanded


class JsonState:
    """A small JSON document on disk, rewritten whole on every change."""

    def __init__(self, path: Path, default: dict[str, Any]):
        self.path = path
        self._lock = threading.Lock()
        self.data = dict(default)
        if path.exists():
            try:
                self.data.update(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                pass  # a corrupt state file falls back to defaults rather than blocking startup

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self.data[key] = value
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
            tmp.replace(self.path)
