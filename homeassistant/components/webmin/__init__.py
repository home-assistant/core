"""The Webmin integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import WebminUpdateCoordinator

PLATFORMS = [Platform.SENSOR]

type WebminConfigEntry = ConfigEntry[WebminUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: WebminConfigEntry) -> None:
    """Set up Webmin from a config entry."""

    coordinator = WebminUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    await coordinator.async_setup()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: WebminConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
