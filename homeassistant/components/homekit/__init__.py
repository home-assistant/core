"""Support for Apple HomeKit.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/homekit/
"""
import logging

import voluptuous as vol

from homeassistant.components.climate import (
    SUPPORT_TARGET_TEMPERATURE_HIGH, SUPPORT_TARGET_TEMPERATURE_LOW)
from homeassistant.const import (
    ATTR_CODE, ATTR_SUPPORTED_FEATURES, ATTR_UNIT_OF_MEASUREMENT,
    CONF_PORT, CONF_ENTITIES, TEMP_CELSIUS, TEMP_FAHRENHEIT,
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import get_local_ip
from homeassistant.util.decorator import Registry
from .const import (
    DOMAIN, HOMEKIT_FILE, CONF_AID, CONF_AUTO_START,
    DEFAULT_PORT, DEFAULT_AUTO_START, SERVICE_HOMEKIT_START)
from .util import (
    validate_entities, show_setup_message)

TYPES = Registry()
_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['HAP-python==1.1.7', 'pypng==0.0.18']


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All({
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
        vol.Optional(CONF_AUTO_START, default=DEFAULT_AUTO_START): cv.boolean,
        vol.Required(CONF_ENTITIES): validate_entities,
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Setup the HomeKit component."""
    _LOGGER.debug("Begin setup HomeKit")

    conf = config[DOMAIN]
    port = conf[CONF_PORT]
    auto_start = conf[CONF_AUTO_START]
    entities = conf[CONF_ENTITIES]

    homekit = HomeKit(hass, port, entities)
    homekit.setup()

    if auto_start:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, homekit.start)
        return True

    def handle_homekit_service_start(service):
        """Handle start HomeKit service call."""
        if homekit.started:
            _LOGGER.warning("HomeKit is already running")
            return
        homekit.start()

    hass.services.async_register(DOMAIN, SERVICE_HOMEKIT_START,
                                 handle_homekit_service_start)

    return True


def get_accessory(hass, state, config):
    """Take state and return an accessory object if supported."""
    if state.domain == 'sensor':
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if unit == TEMP_CELSIUS or unit == TEMP_FAHRENHEIT:
            _LOGGER.debug("Add \"%s\" as \"%s\"",
                          state.entity_id, 'TemperatureSensor')
            return TYPES['TemperatureSensor'](hass, state.entity_id,
                                              state.name, aid=config[CONF_AID])

    elif state.domain == 'cover':
        # Only add covers that support set_cover_position
        if state.attributes.get(ATTR_SUPPORTED_FEATURES, 0) & 4:
            _LOGGER.debug("Add \"%s\" as \"%s\"",
                          state.entity_id, 'WindowCovering')
            return TYPES['WindowCovering'](hass, state.entity_id, state.name,
                                           aid=config[CONF_AID])

    elif state.domain == 'alarm_control_panel':
        _LOGGER.debug("Add \"%s\" as \"%s\"", state.entity_id,
                      'SecuritySystem')
        return TYPES['SecuritySystem'](hass, state.entity_id, state.name,
                                       alarm_code=config[ATTR_CODE],
                                       aid=config[CONF_AID])

    elif state.domain == 'climate':
        features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        support_temp_range = SUPPORT_TARGET_TEMPERATURE_LOW | \
            SUPPORT_TARGET_TEMPERATURE_HIGH
        # Check if climate device supports auto mode
        support_auto = bool(features & support_temp_range)

        _LOGGER.debug("Add \"%s\" as \"%s\"", state.entity_id, 'Thermostat')
        return TYPES['Thermostat'](hass, state.entity_id,
                                   state.name, support_auto,
                                   aid=config[CONF_AID])

    elif state.domain == 'switch' or state.domain == 'remote' \
            or state.domain == 'input_boolean':
        _LOGGER.debug("Add \"%s\" as \"%s\"", state.entity_id, 'Switch')
        return TYPES['Switch'](hass, state.entity_id, state.name,
                               aid=config[CONF_AID])

    _LOGGER.warning("The entity \"%s\" is not supported yet",
                    state.entity_id)
    return None


class HomeKit():
    """Class to handle all actions between HomeKit and Home Assistant."""

    def __init__(self, hass, port, config):
        """Initialize a HomeKit object."""
        self._hass = hass
        self._port = port
        self._config = config
        self.started = False

        self.bridge = None
        self.driver = None

    def setup(self):
        """Setup bridge and accessory driver."""
        from .accessories import HomeBridge, HomeDriver

        self._hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self.stop)

        path = self._hass.config.path(HOMEKIT_FILE)
        self.bridge = HomeBridge(self._hass)
        self.driver = HomeDriver(self.bridge, self._port, get_local_ip(), path)

    def add_bridge_accessory(self, state):
        """Try adding accessory to bridge if configured beforehand."""
        if not state or state.entity_id not in self._config:
            return None
        conf = self._config.pop(state.entity_id)
        acc = get_accessory(self._hass, state, conf)
        if acc is not None:
            self.bridge.add_accessory(acc)

    def start(self, *args):
        """Start the accessory driver."""
        if self.started:
            return
        self.started = True

        # pylint: disable=unused-variable
        from . import (  # noqa F401
            type_covers, type_security_systems, type_sensors,
            type_switches, type_thermostats)

        for state in self._hass.states.all():
            self.add_bridge_accessory(state)
        for entity_id in self._config:
            _LOGGER.warning("The entity \"%s\" was not setup when HomeKit "
                            "was started", entity_id)
        self.bridge.set_broker(self.driver)

        if not self.bridge.paired:
            show_setup_message(self.bridge, self._hass)

        _LOGGER.debug("Driver start")
        self.driver.start()

    def stop(self, *args):
        """Stop the accessory driver."""
        if not self.started:
            return

        _LOGGER.debug("Driver stop")
        if self.driver and self.driver.run_sentinel:
            self.driver.stop()
