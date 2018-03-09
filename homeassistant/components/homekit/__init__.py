"""Support for Apple HomeKit.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/homekit/
"""
import asyncio
import logging
import re

import voluptuous as vol

from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES, ATTR_UNIT_OF_MEASUREMENT, CONF_PORT,
    TEMP_CELSIUS, TEMP_FAHRENHEIT,
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)
from homeassistant.components.climate import (
    SUPPORT_TARGET_TEMPERATURE_HIGH, SUPPORT_TARGET_TEMPERATURE_LOW)
from homeassistant.util import get_local_ip
from homeassistant.util.decorator import Registry

TYPES = Registry()
_LOGGER = logging.getLogger(__name__)

_RE_VALID_PINCODE = r"^(\d{3}-\d{2}-\d{3})$"

DOMAIN = 'homekit'
REQUIREMENTS = ['HAP-python==1.1.7']

BRIDGE_NAME = 'Home Assistant'
CONF_PIN_CODE = 'pincode'

HOMEKIT_FILE = '.homekit.state'


def valid_pin(value):
    """Validate pin code value."""
    match = re.match(_RE_VALID_PINCODE, str(value).strip())
    if not match:
        raise vol.Invalid("Pin must be in the format: '123-45-678'")
    return match.group(0)


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All({
        vol.Optional(CONF_PORT, default=51826): vol.Coerce(int),
        vol.Optional(CONF_PIN_CODE, default='123-45-678'): valid_pin,
    })
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Setup the HomeKit component."""
    _LOGGER.debug("Begin setup HomeKit")

    conf = config[DOMAIN]
    port = conf.get(CONF_PORT)
    pin = str.encode(conf.get(CONF_PIN_CODE))

    homekit = HomeKit(hass, port)
    homekit.setup_bridge(pin)

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_START, homekit.start_driver)
    return True


def import_types():
    """Import all types from files in the HomeKit directory."""
    _LOGGER.debug("Import type files.")
    # pylint: disable=unused-variable
    from . import (  # noqa F401
        covers, security_systems, sensors, switches, thermostats)


def get_accessory(hass, state):
    """Take state and return an accessory object if supported."""
    if state.domain == 'sensor':
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if unit == TEMP_CELSIUS or unit == TEMP_FAHRENHEIT:
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

    elif state.domain == 'alarm_control_panel':
        _LOGGER.debug("Add \"%s\" as \"%s\"", state.entity_id,
                      'SecuritySystem')
        return TYPES['SecuritySystem'](hass, state.entity_id, state.name)

    elif state.domain == 'climate':
        support_auto = False
        features = state.attributes.get(ATTR_SUPPORTED_FEATURES)
        # Check if climate device supports auto mode
        if (features & SUPPORT_TARGET_TEMPERATURE_HIGH) \
                and (features & SUPPORT_TARGET_TEMPERATURE_LOW):
            support_auto = True
        _LOGGER.debug("Add \"%s\" as \"%s\"", state.entity_id, 'Thermostat')
        return TYPES['Thermostat'](hass, state.entity_id,
                                   state.name, support_auto)

    elif state.domain == 'switch' or state.domain == 'remote' \
            or state.domain == 'input_boolean':
        _LOGGER.debug("Add \"%s\" as \"%s\"", state.entity_id, 'Switch')
        return TYPES['Switch'](hass, state.entity_id, state.name)

    return None


class HomeKit():
    """Class to handle all actions between HomeKit and Home Assistant."""

    def __init__(self, hass, port):
        """Initialize a HomeKit object."""
        self._hass = hass
        self._port = port
        self.bridge = None
        self.driver = None

    def setup_bridge(self, pin):
        """Setup the bridge component to track all accessories."""
        from .accessories import HomeBridge
        self.bridge = HomeBridge(BRIDGE_NAME, 'homekit.bridge', pin)

    def start_driver(self, event):
        """Start the accessory driver."""
        from pyhap.accessory_driver import AccessoryDriver
        self._hass.bus.listen_once(
            EVENT_HOMEASSISTANT_STOP, self.stop_driver)

        import_types()
        _LOGGER.debug("Start adding accessories.")
        for state in self._hass.states.all():
            acc = get_accessory(self._hass, state)
            if acc is not None:
                self.bridge.add_accessory(acc)

        ip_address = get_local_ip()
        path = self._hass.config.path(HOMEKIT_FILE)
        self.driver = AccessoryDriver(self.bridge, self._port,
                                      ip_address, path)
        _LOGGER.debug("Driver started")
        self.driver.start()

    def stop_driver(self, event):
        """Stop the accessory driver."""
        _LOGGER.debug("Driver stop")
        if self.driver is not None:
            self.driver.stop()
