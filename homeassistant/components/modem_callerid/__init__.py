"""The Modem Caller ID integration."""
import logging

from phone_modem import PhoneModem

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DATA_KEY_API, DOMAIN, EXCEPTIONS

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [SENSOR_DOMAIN]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Modem Caller ID from a config entry."""
    device = entry.data[CONF_DEVICE]
    try:
        api = PhoneModem(device)
        await api.initialize(device)
    except EXCEPTIONS as ex:
        _LOGGER.error("Unable to open port %s", device)
        raise ConfigEntryNotReady from ex

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_KEY_API: api,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        api = hass.data[DOMAIN].pop(entry.entry_id)[DATA_KEY_API]
        await api.close()

    return unload_ok
