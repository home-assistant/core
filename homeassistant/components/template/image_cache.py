"""Storage of the images restored by template image entities."""

import logging
import pathlib

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, restore_state

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

IMAGES_DIR = "images"


def image_cache_dir(hass: HomeAssistant) -> pathlib.Path:
    """Return the directory of the cached images."""
    return pathlib.Path(hass.config.cache_path(DOMAIN, IMAGES_DIR))


def _prune_image_cache(images_dir: pathlib.Path, keep: set[str]) -> None:
    """Delete cache files that can no longer be restored."""
    try:
        paths = list(images_dir.iterdir())
    except FileNotFoundError:
        return
    except OSError as err:
        _LOGGER.warning("Unable to prune image cache %s: %s", images_dir, err)
        return

    for path in paths:
        if path.suffix not in (".bin", ".tmp") or (
            path.suffix == ".bin" and path.stem in keep
        ):
            continue
        try:
            path.unlink()
        except OSError as err:
            _LOGGER.debug("Unable to prune image cache %s: %s", path, err)


async def async_prune_image_cache(hass: HomeAssistant) -> None:
    """Delete cached images of entities that no longer exist.

    Called once per start, before any template entity is added. Entities deleted
    while not loaded have no removal hook, so a file is kept as long as restore
    state could still restore its entity.
    """
    keep = {
        entry.id
        for entry in er.async_get(hass).entities.values()
        if entry.domain == Platform.IMAGE and entry.platform == DOMAIN
    }
    keep.update(restore_state.async_get(hass).last_states_by_entity_id)
    await hass.async_add_executor_job(_prune_image_cache, image_cache_dir(hass), keep)


def _remove_image_cache_files(paths: list[pathlib.Path]) -> None:
    """Delete cache files."""
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError as err:
            _LOGGER.warning("Unable to remove image cache %s: %s", path, err)


async def async_remove_entry_image_cache(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Delete the cached images of a removed config entry's entities.

    Runs before the entry's registry entries are cleared, which the entities can't
    observe because they are already unloaded.
    """
    images_dir = image_cache_dir(hass)
    paths = [
        images_dir / f"{registry_entry.id}.bin"
        for registry_entry in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
        if registry_entry.domain == Platform.IMAGE
    ]
    await hass.async_add_executor_job(_remove_image_cache_files, paths)
