"""Support for Nest climate that dispatches between API versions."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .climate_sdm import async_setup_sdm_entry
from .const import DATA_SDM
from .legacy.climate import async_setup_legacy_entry


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the climate platform."""
    if DATA_SDM not in entry.data:
        await async_setup_legacy_entry(hass, entry, async_add_entities)
        return
    await async_setup_sdm_entry(hass, entry, async_add_entities)
