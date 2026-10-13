"""The Airobot integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import AirobotConfigEntry, AirobotDataUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: AirobotConfigEntry) -> None:
    """Set up Airobot from a config entry."""
    coordinator = AirobotDataUpdateCoordinator(hass, entry)

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: AirobotConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
