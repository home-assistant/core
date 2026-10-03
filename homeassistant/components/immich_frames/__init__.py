"""The Immich Frames integration."""

from pathlib import Path

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .cache import FrameCache
from .const import (
    CONF_ALBUM_IDS,
    CONF_IMMICH_ENTRY_ID,
    CONF_MODE,
    CONF_ORIENTATION,
    CONF_PAIR_WINDOW,
    CONF_PHOTO_FIT,
    CONF_SCREEN_SHAPE,
    CONF_SMART_QUERY,
    CONF_SOURCE,
    CONF_TIME_RANGE,
    DEFAULT_SOURCE,
    DOMAIN,
)
from .coordinator import ImmichFramesConfigEntry, ImmichFramesDataUpdateCoordinator

PLATFORMS = [Platform.IMAGE]
CONFIG_SCHEMA = cv.config_entry_only_config_schema("immich_frames")
OPTION_KEYS = frozenset(
    {
        CONF_ALBUM_IDS,
        CONF_MODE,
        CONF_ORIENTATION,
        CONF_PAIR_WINDOW,
        CONF_PHOTO_FIT,
        CONF_SCREEN_SHAPE,
        CONF_SMART_QUERY,
        CONF_SOURCE,
        CONF_TIME_RANGE,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Immich Frames integration."""
    return True


async def async_migrate_entry(
    hass: HomeAssistant, entry: ImmichFramesConfigEntry
) -> bool:
    """Migrate an older frame entry to the current source model."""
    if entry.version < 2:
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_SOURCE: entry.data.get(CONF_SOURCE, DEFAULT_SOURCE),
            },
            version=2,
        )
    if entry.version < 3:
        moved_options = {
            key: value
            for key, value in entry.data.items()
            if key in OPTION_KEYS and key not in entry.options
        }
        hass.config_entries.async_update_entry(
            entry,
            data={
                key: value
                for key, value in entry.data.items()
                if key not in OPTION_KEYS
            },
            options={**moved_options, **entry.options},
            version=3,
        )
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ImmichFramesConfigEntry
) -> bool:
    """Set up an Immich frame."""
    immich_entry = hass.config_entries.async_get_entry(entry.data[CONF_IMMICH_ENTRY_ID])
    if immich_entry is None or immich_entry.state is not ConfigEntryState.LOADED:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="immich_not_ready",
        )
    try:
        coordinator = ImmichFramesDataUpdateCoordinator(hass, entry)
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady as err:
        if err.translation_key != "no_photos":
            raise
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ImmichFramesConfigEntry
) -> bool:
    """Unload an Immich frame without closing the shared Immich client."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(
    hass: HomeAssistant, entry: ImmichFramesConfigEntry
) -> None:
    """Remove the private cached image for a deleted frame."""
    cache = FrameCache(
        Path(hass.config.path(".storage", f"immich_frames_{entry.entry_id}.json"))
    )
    await hass.async_add_executor_job(cache.clear)
