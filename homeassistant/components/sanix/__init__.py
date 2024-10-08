"""The Sanix integration."""

from sanix import Sanix

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_SERIAL_NUMBER, DOMAIN
from .coordinator import SanixCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sanix from a config entry."""

    serial_no = entry.data[CONF_SERIAL_NUMBER]
    token = entry.data[CONF_TOKEN]

    sanix_api = Sanix(serial_no, token)
    coordinator = SanixCoordinator(hass, sanix_api)

    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
