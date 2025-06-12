"""The Paperless-ngx integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import PaperlessConfigEntry, PaperlessCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: PaperlessConfigEntry) -> bool:
    """Set up Paperless-ngx from a config entry."""

    coordinator = PaperlessCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PaperlessConfigEntry) -> bool:
    """Unload paperless-ngx config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
