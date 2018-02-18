"""Support for Apple Homekit.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/homekit/
"""
import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    ATTR_FRIENDLY_NAME, ATTR_SUPPORTED_FEATURES, CONF_PATH, CONF_PORT,
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)
from homeassistant.util import get_local_ip
from homeassistant.util.decorator import Registry

TYPES = Registry()
_LOGGER = logging.getLogger(__name__)

DOMAIN = 'homekit'
REQUIREMENTS = ['HAP-python==1.1.2']

BRIDGE_NAME = 'Home Assistant'
CONF_PIN_CODE = 'pincode'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All({
        vol.Optional(CONF_PORT, default=51826): vol.Coerce(int),
        vol.Optional(CONF_PIN_CODE, default='123-45-678'): cv.string,
        vol.Optional(CONF_PATH, default='accessory.state'): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Setup the homekit component."""
    # pylint: disable=unused-variable
    from .covers import Window  # noqa F401
    # pylint: disable=unused-variable
    from .sensors import TemperatureSensor # noqa F401

    conf = config[DOMAIN]
    port = conf.get(CONF_PORT)
    pin = str.encode(conf.get(CONF_PIN_CODE))
    path = hass.config.path(conf.get(CONF_PATH))

    ip_address = get_local_ip()

    homekit = Homekit(ip_address, port, path)
    homekit.setup_bridge(BRIDGE_NAME, pin)

    _LOGGER.debug('Start adding accessories.')
    for state in hass.states.async_all():
        if state.domain == 'cover':
            # Only add covers that support set_cover_position
            if not state.attributes.get(ATTR_SUPPORTED_FEATURES) & 4:
                continue
            _LOGGER.debug('Add \"%s\" as \"%s\"',
                          state.entity_id, 'Window')
            name = state.attributes.get(ATTR_FRIENDLY_NAME, 'cover')
            acc = TYPES['Window'](hass, state.entity_id, name)
            homekit.add_accessory(acc)
            continue
        if state.domain == 'sensor':
            _LOGGER.debug('Add \"%s\" as \"%s\"',
                          state.entity_id, 'TemperatureSensor')
            name = state.attributes.get(ATTR_FRIENDLY_NAME, 'sensor')
            acc = TYPES['TemperatureSensor'](hass, state.entity_id, name)
            homekit.add_accessory(acc)
            continue

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_START, homekit.start_driver)
    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, homekit.stop_driver)

    return True


class Homekit():
    """Class to handle all actions between homekit and Home Assistant."""

    def __init__(self, ip_address, port, path):
        """Initialize a homekit object."""
        self._ip_address = ip_address
        self._port = port
        self._path = path
        self.bridge = None
        self.driver = None

    def setup_bridge(self, name, pin):
        """Setup the bridge component to track all accessories."""
        from .accessories import HomeBridge
        self.bridge = HomeBridge(name, pincode=pin)
        self.bridge.set_accessory_info('homekit.bridge')

    def add_accessory(self, acc):
        """Add an accessory to the bridge."""
        self.bridge.add_accessory(acc)

    def start_driver(self, event):
        """Start the accessory driver."""
        from pyhap.accessory_driver import AccessoryDriver
        self.driver = AccessoryDriver(self.bridge, self._port,
                                      self._ip_address, self._path)
        _LOGGER.debug('Driver start')
        self.driver.start()

    def stop_driver(self, event):
        """Stop the accessory driver."""
        _LOGGER.debug('Driver stop')
        self.driver.stop()
