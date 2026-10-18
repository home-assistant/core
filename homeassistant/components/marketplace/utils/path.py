"""Path utils."""

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.helpers.storage import STORAGE_DIR

from ..const import DOMAIN
from ..exceptions import MarketplaceError

if TYPE_CHECKING:
    from ..base import MarketplaceManager


@lru_cache(maxsize=1)
def _get_safe_paths(
    config_path: str,
    plugin_path: str,
    theme_path: str,
) -> set[str]:
    """Get safe paths."""
    return {
        Path(config_path).resolve().as_posix(),
        Path(f"{config_path}/{STORAGE_DIR}").resolve().as_posix(),
        Path(f"{config_path}/{plugin_path}").resolve().as_posix(),
        # What the retired python_script category installed still runs from here
        Path(f"{config_path}/python_scripts/").resolve().as_posix(),
        Path(f"{config_path}/{theme_path}").resolve().as_posix(),
        Path(f"{config_path}/custom_components/").resolve().as_posix(),
        Path(f"{config_path}/custom_templates/").resolve().as_posix(),
    }


def is_safe(marketplace: MarketplaceManager, path: str | Path) -> bool:
    """Helper to check if path is safe to remove."""
    configuration = marketplace.configuration
    return Path(path).resolve().as_posix() not in _get_safe_paths(
        marketplace.core.config_path,
        configuration.plugin_path,
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
        raise MarketplaceError(
            translation_domain=DOMAIN,
            translation_key="path_outside_directory",
            translation_placeholders={
                "path": str(path),
                "directory": str(resolved_directory),
            },
        )

    return resolved


def entry_in_directory(directory: str | Path, path: str | Path) -> Path:
    """Require the path to be an entry of directory, without following it.

    An install can be a symlink, the link is what belongs to the directory
    and not what it points at.
    """
    path = Path(path)
    if path.name in ("", ".", ".."):
        raise MarketplaceError(
            translation_domain=DOMAIN,
            translation_key="path_outside_directory",
            translation_placeholders={"path": str(path), "directory": str(directory)},
        )

    return resolve_in_directory(directory, path.parent) / path.name
