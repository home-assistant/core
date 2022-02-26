"""Support for Ebusd daemon for communication with eBUS heating systems."""
from __future__ import annotations

import logging

import ebusdpy
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import CONF_CACHE_TTL, CONF_CIRCUIT, DOMAIN, SERVICE_EBUSD_WRITE

_LOGGER = logging.getLogger(__name__)

CONF_VALUE = "value"
SERVICE_EBUSD_WRITE_SCHEMA = vol.Schema(
    {vol.Required(CONF_NAME): cv.string, vol.Required(CONF_VALUE): cv.string}
)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ebusd from a config entry."""
    server_address = (entry.data[CONF_HOST], entry.data[CONF_PORT])
    ebus_data = EbusdData(
        server_address, entry.data[CONF_CIRCUIT], entry.data[CONF_CACHE_TTL]
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = ebus_data

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    async def ebusd_write(call: ServiceCall) -> None:
        """Service call to write to ebusd."""
        await ebus_data.write(name=call.data[CONF_NAME], value=call.data[CONF_VALUE])

    hass.services.async_register(
        DOMAIN, SERVICE_EBUSD_WRITE, ebusd_write, schema=SERVICE_EBUSD_WRITE_SCHEMA
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.services.async_remove(DOMAIN, SERVICE_EBUSD_WRITE)

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class EbusdData:
    """Get the latest data from Ebusd."""

    def __init__(self, address, circuit, cache_ttl):
        """Initialize the data object."""
        self._circuit = circuit
        self._address = address
        self.cache_ttl = cache_ttl
        self.value = {}

    def update(self, name, stype):
        """Call the ebusd API to update the data."""
        try:
            _LOGGER.debug("Opening socket to ebusd %s", name)
            command_result = ebusdpy.read(
                self._address, self._circuit, name, stype, self.cache_ttl
            )
            if command_result is not None:
                if "ERR:" in command_result:
                    _LOGGER.warning(command_result)
                else:
                    self.value[name] = command_result
        except Exception as err:
            _LOGGER.exception(err)
            raise RuntimeError(err) from err

    def write(self, *, name: str, value: str):
        """Call write method on ebusd."""
        try:
            _LOGGER.debug("Opening socket to ebusd %s", name)
            command_result = ebusdpy.write(self._address, self._circuit, name, value)
            if command_result is not None and "done" not in command_result:
                _LOGGER.warning("Write command failed: %s", name)
        except Exception as err:
            _LOGGER.exception(err)
            raise RuntimeError(err) from err
