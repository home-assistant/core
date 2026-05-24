"""The HDFury Integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import HDFuryConfigEntry, async_create_runtime_data

PLATFORMS = [
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: HDFuryConfigEntry) -> bool:
    """Set up HDFury as config entry."""

    entry.runtime_data = await async_create_runtime_data(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HDFuryConfigEntry) -> bool:
    """Unload a HDFury config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
