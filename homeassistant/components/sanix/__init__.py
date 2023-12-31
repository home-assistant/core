"""The Sanix integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_SERIAL_NO, CONF_TOKEN, DOMAIN
from .coordinator import SanixCoordinator
from .sanix import Sanix

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sanix from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    _serial_no = entry.data[CONF_SERIAL_NO]
    _token = entry.data[CONF_TOKEN]

    sanix_api = Sanix(_serial_no, _token, async_get_clientsession(hass))
    coordinator = SanixCoordinator(hass, sanix_api)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.config_entries.async_update_entry(entry, unique_id=_serial_no)

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
