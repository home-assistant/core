"""Helpers for reading integration icon files."""

import contextlib

from astroid import nodes
import orjson

from .integration import get_integration_dir

_icons_cache: dict[str, dict | None] = {}


def clear_icons_cache() -> None:
    """Clear the icons cache (used by tests)."""
    _icons_cache.clear()


def load_icons(module: nodes.Module) -> dict | None:
    """Load and cache the icons.json for the current integration.

    Returns the parsed JSON as a dict, or ``None`` if not found.
    """
    integration_dir = get_integration_dir(module)
    if integration_dir is None:
        return None

    cache_key = str(integration_dir)
    if cache_key in _icons_cache:
        return _icons_cache[cache_key]

    icons_path = integration_dir / "icons.json"
    result: dict | None = None
    if icons_path.exists():
        with contextlib.suppress(orjson.JSONDecodeError, OSError):
            parsed = orjson.loads(icons_path.read_bytes())
            if isinstance(parsed, dict):
                result = parsed

    _icons_cache[cache_key] = result
    return result


def collect_mdi_icons(
    data: dict | list | str, icons: set[str] | None = None
) -> set[str]:
    """Recursively collect all mdi: icon references from a data structure."""
    if icons is None:
        icons = set()

    if isinstance(data, str):
        if data.startswith("mdi:"):
            icons.add(data)
    elif isinstance(data, dict):
        for value in data.values():
            collect_mdi_icons(value, icons)
    elif isinstance(data, list):
        for item in data:
            collect_mdi_icons(item, icons)

    return icons
