"""The Phone Modem integration."""
import asyncio
import logging

from phone_modem import PhoneModem, exceptions
import serial

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DATA_KEY_API, DOMAIN

_LOGGER = logging.getLogger(__name__)


PLATFORMS = [SENSOR_DOMAIN]


async def async_setup(hass: HomeAssistant, config):
    """Set up the Phone Modem component."""
    hass.data[DOMAIN] = {}

    return True


async def async_setup_entry(hass, entry):
    """Set up Phone Modem from a config entry."""
    port = entry.data[CONF_PORT]
    try:
        api = PhoneModem(port)
    except (
        FileNotFoundError,
        exceptions.SerialError,
        serial.SerialException,
        serial.serialutil.SerialException,
    ) as ex:
        _LOGGER.error("Unable to open port %s", port)
        raise ConfigEntryNotReady from ex

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_KEY_API: api,
    }

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
