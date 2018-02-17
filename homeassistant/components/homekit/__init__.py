"""Support for Apple Homekit.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/homekit/
"""
import asyncio
import logging

import voluptuous as vol

from pyhap.accessory_driver import AccessoryDriver

from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_NAME, CONF_IP_ADDRESS, CONF_PORT,
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent

from .accessories import HomeBridge
from .covers import Window
from .sensors import TemperatureSensor


_LOGGER = logging.getLogger(__name__)

DOMAIN = 'homekit'
REQUIREMENTS = ['HAP-python==1.1.2']

ATTR_CLASS = 'class'
ATTR_NAME = 'name'

CONF_PIN_CODE = 'pincode'
CONF_TYPES = 'types'

ALL_TYPES = {
    'sensor_temperature': {ATTR_NAME: 'Temperature',
                           ATTR_CLASS: TemperatureSensor},
    'cover': {ATTR_NAME: 'Cover',
              ATTR_CLASS: Window},
}


def valid_typ(value):
    """Check if typ is valid."""
    if value.lower() in ALL_TYPES.keys():
        return value.lower()
    raise vol.Invalid('Typ {} is an invalid typ.'.format(value))


def valid_string(string):
    """Check if name string is valid. An empty string is allowed."""
    if string is None:
        return None
    return str(string)


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All({
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_IP_ADDRESS): cv.string,
        vol.Optional(CONF_PORT): vol.Coerce(int),
        vol.Optional(CONF_PIN_CODE): cv.string,
        vol.Required(CONF_TYPES): vol.Schema({
            vol.Required(valid_typ): vol.Schema({
                vol.Required(cv.entity_id): valid_string,
            })
        })
    })
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Setup the homekit component."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    conf = config[DOMAIN]
    name = conf.get(CONF_NAME, 'homeassistant')
    ip_address = conf.get(CONF_IP_ADDRESS, '127.0.0.1')
    port = conf.get(CONF_PORT, 51826)
    pin = conf.get(CONF_PIN_CODE, '123-45-678')
    types = conf.get(CONF_TYPES)

    yield from component.async_add_entities([
        Homekit(hass, name, ip_address, port, pin, types)])
    return True


class Homekit(Entity):
    """Class to handle all actions between homekit and Home Assistant."""

    def __init__(self, hass, name, ip_address, port, pin, types):
        """Initialize a homekit entity."""
        self._hass = hass
        self._name = name
        self._ip_address = ip_address
        self._port = port
        self._pin = str.encode(pin)
        self._types = types
        self.path = self._hass.config.path('accessory.state')
        self.bridge = None
        self.driver = None

    def setup_bridge(self):
        """Setup the bridge component to track all accessories."""
        self.bridge = HomeBridge(self._name, pincode=self._pin)
        self.bridge.set_accessory_info('homekit.bridge')

    def setup_accessories(self):
        """Setup all accessories to be available in homekit."""
        for typ, entities in self._types.items():
            for entity_id, name in entities.items():
                if name is None:
                    name = ALL_TYPES[typ][ATTR_NAME]
                acc = ALL_TYPES[typ][ATTR_CLASS](
                    self.hass, entity_id, display_name=name)
                self.bridge.add_accessory(acc)

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def start_driver(event):
            """Start the accessory driver after HA start is called."""
            self.setup_bridge()
            self.setup_accessories()
            _LOGGER.debug('Driver start')
            self.driver = AccessoryDriver(self.bridge, self._port,
                                          self._ip_address, self.path)
            self.driver.start()

        @callback
        def homeassistant_stop(event):
            """Stop the accessory drive after HA stop is called."""
            _LOGGER.debug('Driver stop')
            self.driver.stop()

        self._hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, start_driver)
        self._hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, homeassistant_stop)
