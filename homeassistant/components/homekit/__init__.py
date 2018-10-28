"""Support for Apple HomeKit.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/homekit/
"""
import ipaddress
import logging
from zlib import adler32

import voluptuous as vol

from homeassistant.components import cover
from homeassistant.const import (
    ATTR_DEVICE_CLASS, ATTR_SUPPORTED_FEATURES, ATTR_UNIT_OF_MEASUREMENT,
    CONF_IP_ADDRESS, CONF_NAME, CONF_PORT, CONF_TYPE, DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE, DEVICE_CLASS_TEMPERATURE,
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP,
    TEMP_CELSIUS, TEMP_FAHRENHEIT)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import FILTER_SCHEMA
from homeassistant.util import get_local_ip
from homeassistant.util.decorator import Registry
from .const import (
    BRIDGE_NAME, CONF_AUTO_START, CONF_ENTITY_CONFIG, CONF_FEATURE_LIST,
    CONF_FILTER, DEFAULT_AUTO_START, DEFAULT_PORT, DEVICE_CLASS_CO,
    DEVICE_CLASS_CO2, DEVICE_CLASS_PM25, DOMAIN, HOMEKIT_FILE,
    SERVICE_HOMEKIT_START, TYPE_FAUCET, TYPE_OUTLET, TYPE_SHOWER,
    TYPE_SPRINKLER, TYPE_SWITCH, TYPE_VALVE)
from .util import (
    show_setup_message, validate_entity_config, validate_media_player_features)

REQUIREMENTS = ['HAP-python==2.3.0']

_LOGGER = logging.getLogger(__name__)

MAX_DEVICES = 100
TYPES = Registry()

# #### Driver Status ####
STATUS_READY = 0
STATUS_RUNNING = 1
STATUS_STOPPED = 2
STATUS_WAIT = 3

SWITCH_TYPES = {
    TYPE_FAUCET: 'Valve',
    TYPE_OUTLET: 'Outlet',
    TYPE_SHOWER: 'Valve',
    TYPE_SPRINKLER: 'Valve',
    TYPE_SWITCH: 'Switch',
    TYPE_VALVE: 'Valve'}

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All({
        vol.Optional(CONF_NAME, default=BRIDGE_NAME):
            vol.All(cv.string, vol.Length(min=3, max=25)),
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_IP_ADDRESS):
            vol.All(ipaddress.ip_address, cv.string),
        vol.Optional(CONF_AUTO_START, default=DEFAULT_AUTO_START): cv.boolean,
        vol.Optional(CONF_FILTER, default={}): FILTER_SCHEMA,
        vol.Optional(CONF_ENTITY_CONFIG, default={}): validate_entity_config,
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the HomeKit component."""
    _LOGGER.debug('Begin setup HomeKit')

    conf = config[DOMAIN]
    name = conf[CONF_NAME]
    port = conf[CONF_PORT]
    ip_address = conf.get(CONF_IP_ADDRESS)
    auto_start = conf[CONF_AUTO_START]
    entity_filter = conf[CONF_FILTER]
    entity_config = conf[CONF_ENTITY_CONFIG]

    homekit = HomeKit(hass, name, port, ip_address, entity_filter,
                      entity_config)
    await hass.async_add_executor_job(homekit.setup)

    if auto_start:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, homekit.start)
        return True

    def handle_homekit_service_start(service):
        """Handle start HomeKit service call."""
        if homekit.status != STATUS_READY:
            _LOGGER.warning(
                'HomeKit is not ready. Either it is already running or has '
                'been stopped.')
            return
        homekit.start()

    hass.services.async_register(DOMAIN, SERVICE_HOMEKIT_START,
                                 handle_homekit_service_start)

    return True


def get_accessory(hass, driver, state, aid, config):
    """Take state and return an accessory object if supported."""
    if not aid:
        _LOGGER.warning('The entitiy "%s" is not supported, since it '
                        'generates an invalid aid, please change it.',
                        state.entity_id)
        return None

    a_type = None
    name = config.get(CONF_NAME, state.name)

    if state.domain == 'alarm_control_panel':
        a_type = 'SecuritySystem'

    elif state.domain == 'binary_sensor' or state.domain == 'device_tracker':
        a_type = 'BinarySensor'

    elif state.domain == 'climate':
        a_type = 'Thermostat'

    elif state.domain == 'cover':
        device_class = state.attributes.get(ATTR_DEVICE_CLASS)
        features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        if device_class == 'garage' and \
                features & (cover.SUPPORT_OPEN | cover.SUPPORT_CLOSE):
            a_type = 'GarageDoorOpener'
        elif features & cover.SUPPORT_SET_POSITION:
            a_type = 'WindowCovering'
        elif features & (cover.SUPPORT_OPEN | cover.SUPPORT_CLOSE):
            a_type = 'WindowCoveringBasic'

    elif state.domain == 'fan':
        a_type = 'Fan'

    elif state.domain == 'light':
        a_type = 'Light'

    elif state.domain == 'lock':
        a_type = 'Lock'

    elif state.domain == 'media_player':
        feature_list = config.get(CONF_FEATURE_LIST)
        if feature_list and \
                validate_media_player_features(state, feature_list):
            a_type = 'MediaPlayer'

    elif state.domain == 'sensor':
        device_class = state.attributes.get(ATTR_DEVICE_CLASS)
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

        if device_class == DEVICE_CLASS_TEMPERATURE or \
                unit in (TEMP_CELSIUS, TEMP_FAHRENHEIT):
            a_type = 'TemperatureSensor'
        elif device_class == DEVICE_CLASS_HUMIDITY and unit == '%':
            a_type = 'HumiditySensor'
        elif device_class == DEVICE_CLASS_PM25 \
                or DEVICE_CLASS_PM25 in state.entity_id:
            a_type = 'AirQualitySensor'
        elif device_class == DEVICE_CLASS_CO:
            a_type = 'CarbonMonoxideSensor'
        elif device_class == DEVICE_CLASS_CO2 \
                or DEVICE_CLASS_CO2 in state.entity_id:
            a_type = 'CarbonDioxideSensor'
        elif device_class == DEVICE_CLASS_ILLUMINANCE or unit in ('lm', 'lx'):
            a_type = 'LightSensor'

    elif state.domain == 'switch':
        switch_type = config.get(CONF_TYPE, TYPE_SWITCH)
        a_type = SWITCH_TYPES[switch_type]

    elif state.domain in ('automation', 'input_boolean', 'remote', 'script'):
        a_type = 'Switch'

    elif state.domain == 'water_heater':
        a_type = 'WaterHeater'

    if a_type is None:
        return None

    _LOGGER.debug('Add "%s" as "%s"', state.entity_id, a_type)
    return TYPES[a_type](hass, driver, name, state.entity_id, aid, config)


def generate_aid(entity_id):
    """Generate accessory aid with zlib adler32."""
    aid = adler32(entity_id.encode('utf-8'))
    if aid in (0, 1):
        return None
    return aid


class HomeKit():
    """Class to handle all actions between HomeKit and Home Assistant."""

    def __init__(self, hass, name, port, ip_address, entity_filter,
                 entity_config):
        """Initialize a HomeKit object."""
        self.hass = hass
        self._name = name
        self._port = port
        self._ip_address = ip_address
        self._filter = entity_filter
        self._config = entity_config
        self.status = STATUS_READY

        self.bridge = None
        self.driver = None

    def setup(self):
        """Set up bridge and accessory driver."""
        from .accessories import HomeBridge, HomeDriver

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self.stop)

        ip_addr = self._ip_address or get_local_ip()
        path = self.hass.config.path(HOMEKIT_FILE)
        self.driver = HomeDriver(self.hass, address=ip_addr,
                                 port=self._port, persist_file=path)
        self.bridge = HomeBridge(self.hass, self.driver, self._name)

    def add_bridge_accessory(self, state):
        """Try adding accessory to bridge if configured beforehand."""
        if not state or not self._filter(state.entity_id):
            return
        aid = generate_aid(state.entity_id)
        conf = self._config.pop(state.entity_id, {})
        acc = get_accessory(self.hass, self.driver, state, aid, conf)
        if acc is not None:
            self.bridge.add_accessory(acc)

    def start(self, *args):
        """Start the accessory driver."""
        if self.status != STATUS_READY:
            return
        self.status = STATUS_WAIT

        # pylint: disable=unused-variable
        from . import (  # noqa F401
            type_covers, type_fans, type_lights, type_locks,
            type_media_players, type_security_systems, type_sensors,
            type_switches, type_thermostats)

        for state in self.hass.states.all():
            self.add_bridge_accessory(state)
        self.driver.add_accessory(self.bridge)

        if not self.driver.state.paired:
            show_setup_message(self.hass, self.driver.state.pincode)

        if len(self.bridge.accessories) > MAX_DEVICES:
            _LOGGER.warning('You have exceeded the device limit, which might '
                            'cause issues. Consider using the filter option.')

        _LOGGER.debug('Driver start')
        self.hass.add_job(self.driver.start)
        self.status = STATUS_RUNNING

    def stop(self, *args):
        """Stop the accessory driver."""
        if self.status != STATUS_RUNNING:
            return
        self.status = STATUS_STOPPED

        _LOGGER.debug('Driver stop')
        self.hass.add_job(self.driver.stop)
