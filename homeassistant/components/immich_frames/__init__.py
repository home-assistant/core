"""The Immich Frames integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .coordinator import ImmichFramesConfigEntry, ImmichFramesDataUpdateCoordinator

PLATFORMS = [Platform.BUTTON, Platform.IMAGE, Platform.SENSOR, Platform.SWITCH]
CONFIG_SCHEMA = cv.config_entry_only_config_schema("immich_frames")


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Immich Frames integration."""
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ImmichFramesConfigEntry) -> bool:
    """Migrate an older frame entry to the current source model."""
    if entry.version < 2:
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, "source": "all"},
            version=2,
        )
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ImmichFramesConfigEntry
) -> bool:
    """Set up an Immich frame."""
    coordinator = ImmichFramesDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ImmichFramesConfigEntry
) -> bool:
    """Unload an Immich frame without closing the shared Immich client."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
