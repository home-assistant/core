"""SmartTub integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .controller import SmartTubConfigEntry, SmartTubController

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: SmartTubConfigEntry) -> bool:
    """Set up a smarttub config entry."""

    controller = SmartTubController(hass)

    if not await controller.async_setup_entry(entry):
        return False

    entry.runtime_data = controller

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SmartTubConfigEntry) -> bool:
    """Remove a smarttub config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
