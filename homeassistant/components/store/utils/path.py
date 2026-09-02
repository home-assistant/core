"""Path utils."""

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.helpers.storage import STORAGE_DIR

from ..exceptions import HacsException

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
        Path(config_path).resolve().as_posix(),
        Path(f"{config_path}/{STORAGE_DIR}").resolve().as_posix(),
        Path(f"{config_path}/{appdaemon_path}").resolve().as_posix(),
        Path(f"{config_path}/{plugin_path}").resolve().as_posix(),
        Path(f"{config_path}/{python_script_path}").resolve().as_posix(),
        Path(f"{config_path}/{theme_path}").resolve().as_posix(),
        Path(f"{config_path}/custom_components/").resolve().as_posix(),
        Path(f"{config_path}/custom_templates/").resolve().as_posix(),
    }


def is_safe(hacs: HacsBase, path: str | Path) -> bool:
    """Helper to check if path is safe to remove."""
    configuration = hacs.configuration
    return Path(path).resolve().as_posix() not in _get_safe_paths(
        hacs.core.config_path,
        configuration.appdaemon_path,
        configuration.plugin_path,
        configuration.python_script_path,
        configuration.theme_path,
    )


def resolve_in_directory(directory: str | Path, path: str | Path) -> Path:
    """Resolve path and require it to stay inside directory.

    File names taken from a repository (hacs.json, the repository tree, the
    members of a ZIP archive) are remote input, so the resolved target has to
    be checked instead of trusted.
    """
    resolved_directory = Path(directory).resolve()
    resolved = Path(directory, path).resolve()

    if resolved != resolved_directory and resolved_directory not in resolved.parents:
        raise HacsException(f"'{path}' is not inside {resolved_directory}")

    return resolved
