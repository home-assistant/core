"""Path utils"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..base import HacsBase


@lru_cache(maxsize=1)
def _get_safe_paths(
    config_path: str,
    appdaemon_path: str,
    plugin_path: str,
    python_script_path: str,
    theme_path: str,
) -> set[str]:
    """Get safe paths."""
    return {
        Path(f"{config_path}/{appdaemon_path}").as_posix(),
        Path(f"{config_path}/{plugin_path}").as_posix(),
        Path(f"{config_path}/{python_script_path}").as_posix(),
        Path(f"{config_path}/{theme_path}").as_posix(),
        Path(f"{config_path}/custom_components/").as_posix(),
        Path(f"{config_path}/custom_templates/").as_posix(),
    }


def is_safe(hacs: HacsBase, path: str | Path) -> bool:
    """Helper to check if path is safe to remove."""
    configuration = hacs.configuration
    return Path(path).as_posix() not in _get_safe_paths(
        hacs.core.config_path,
        configuration.appdaemon_path,
        configuration.plugin_path,
        configuration.python_script_path,
        configuration.theme_path,
    )
