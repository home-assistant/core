"""Support for Apple Homekit.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/homekit/
"""
import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES, ATTR_UNIT_OF_MEASUREMENT, CONF_PORT, TEMP_CELSIUS,
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)
from homeassistant.util import get_local_ip
from homeassistant.util.decorator import Registry

TYPES = Registry()
_LOGGER = logging.getLogger(__name__)

DOMAIN = 'homekit'
REQUIREMENTS = ['HAP-python==1.1.5']

BRIDGE_NAME = 'Home Assistant'
CONF_PIN_CODE = 'pincode'

HOMEKIT_FILE = '.homekit.state'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All({
        vol.Optional(CONF_PORT, default=51826): vol.Coerce(int),
        vol.Optional(CONF_PIN_CODE, default='123-45-678'): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Setup the homekit component."""
    # pylint: disable=unused-variable
    from .covers import Window  # noqa F401
    # pylint: disable=unused-variable
    from .sensors import TemperatureSensor # noqa F401
    _LOGGER.debug("Begin setup homekit")

    conf = config[DOMAIN]
    port = conf.get(CONF_PORT)
    pin = str.encode(conf.get(CONF_PIN_CODE))

    homekit = Homekit(hass, port)
    homekit.setup_bridge(pin)

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_START, homekit.start_driver)
    return True


def get_accessory(hass, state):
    """Take state and return an accessory object if supported."""
    if state.domain == 'sensor':
        if state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TEMP_CELSIUS:
            _LOGGER.debug("Add \"%s\" as \"%s\"",
                          state.entity_id, 'TemperatureSensor')
            return TYPES['TemperatureSensor'](hass, state.entity_id,
                                              state.name)

    elif state.domain == 'cover':
        # Only add covers that support set_cover_position
        if state.attributes.get(ATTR_SUPPORTED_FEATURES) & 4:
            _LOGGER.debug("Add \"%s\" as \"%s\"",
                          state.entity_id, 'Window')
            return TYPES['Window'](hass, state.entity_id, state.name)

    return None


class Homekit():
    """Class to handle all actions between homekit and Home Assistant."""

    def __init__(self, hass, port):
        """Initialize a homekit object."""
        self._hass = hass
        self._port = port
        self.bridge = None
        self.driver = None

    def setup_bridge(self, pin):
        """Setup the bridge component to track all accessories."""
        from .accessories import HomeBridge
        self.bridge = HomeBridge(BRIDGE_NAME, pincode=pin)
        self.bridge.set_accessory_info('homekit.bridge')

    def add_accessory(self, acc):
        """Add an accessory to the bridge."""
        self.bridge.add_accessory(acc)

    def start_driver(self, event):
        """Start the accessory driver."""
        from pyhap.accessory_driver import AccessoryDriver
        _LOGGER.debug('Start driver')
        self._hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self.stop_driver)

        _LOGGER.debug('Start adding accessories.')
        for state in self._hass.states.async_all():
            acc = get_accessory(self._hass, state)
            if acc is not None:
                self.bridge.add_accessory(acc)

        ip_address = get_local_ip()
        # ip_address = yield from self._hass.async_add_job(get_local_ip)
        path = self._hass.config.path(HOMEKIT_FILE)
        self.driver = AccessoryDriver(self.bridge, self._port,
                                      ip_address, path)
        _LOGGER.debug('Driver started')
        self.driver.start()

    def stop_driver(self, event):
        """Stop the accessory driver."""
        _LOGGER.debug('Driver stop')
        if self.driver is not None:
            self.driver.stop()
