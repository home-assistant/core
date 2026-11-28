"""The met_eireann component."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import MetEireannConfigEntry, MetEireannUpdateCoordinator

PLATFORMS = [Platform.WEATHER]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: MetEireannConfigEntry
) -> None:
    """Set up Met Éireann as config entry."""
    coordinator = MetEireannUpdateCoordinator(hass, config_entry=config_entry)
    await coordinator.async_refresh()

    config_entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, config_entry: MetEireannConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(config_entry, PLATFORMS)
