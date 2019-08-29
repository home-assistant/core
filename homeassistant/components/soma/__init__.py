"""Support for Soma Smartshades."""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries
from homeassistant.components.soma import config_flow
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from homeassistant.const import (
    CONF_HOST, CONF_PORT)

from .const import DOMAIN, HOST, API

DEVICES = 'devices'

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.string
    })
}, extra=vol.ALLOW_EXTRA)

SOMA_COMPONENTS = ['cover']


async def async_setup(hass, config):
    """Set up the Soma component."""
    if DOMAIN not in config:
        return True

    hass.data[DOMAIN] = {}

    config_flow.register_flow_implementation(
        hass, config[DOMAIN][CONF_HOST],
        config[DOMAIN][CONF_PORT])

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={'source': config_entries.SOURCE_IMPORT},
        ))

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Set up Soma from a config entry."""
    from api.soma_api import SomaApi
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][API] = SomaApi(entry.data[HOST])
    ret = await hass.async_add_executor_job(
        hass.data[DOMAIN][API].list_devices)
    hass.data[DOMAIN][DEVICES] = ret['shades']

    for component in SOMA_COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component))

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Unload a config entry."""
    return True


class SomaEntity(Entity):
    """Representation of a generic Soma device."""

    def __init__(self, device, api):
        """Initialize the Soma device."""
        self.device = device
        self.api = api
        self.current_position = 50

    @property
    def unique_id(self):
        """Return the unique id base on the id returned by pysoma API."""
        return self.device['mac']

    @property
    def name(self):
        """Return the name of the device."""
        return self.device['name']

    @property
    def device_info(self):
        """Return device specific attributes.

        Implemented by platform classes.
        """
        return {
            'identifiers': {(DOMAIN, self.unique_id)},
            'name': self.name,
            'manufacturer': 'Wazombi Labs'
        }

    async def async_update(self):
        """Update the device with the latest data."""
        ret = await self.hass.async_add_executor_job(
            self.api.get_shade_state, self.device['mac'])
        self.current_position = ret['position']

    def has_capability(self, capability):
        """Test if device has a capability."""
        capabilities = self.device.capabilities
        return bool([c for c in capabilities if c.name == capability])
