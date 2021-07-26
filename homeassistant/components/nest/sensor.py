"""Support for Nest sensors that dispatches between API versions."""

from typing import Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DATA_SDM
from .legacy.sensor import async_setup_legacy_entry
from .sensor_sdm import async_setup_sdm_entry


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors."""
    if DATA_SDM not in entry.data:
        await async_setup_legacy_entry(hass, entry, async_add_entities)
        return

    await async_setup_sdm_entry(hass, entry, async_add_entities)
