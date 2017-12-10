"""
Platform for the Daikin AC.

For more details about this component, please refer to the documentation
https://home-assistant.io/components/daikin/
"""
import logging
import time
from socket import timeout
from threading import Lock

import voluptuous as vol

from homeassistant.components.climate import (
    ATTR_OPERATION_MODE, ATTR_SWING_MODE,
    ATTR_TEMPERATURE, ATTR_CURRENT_TEMPERATURE, ATTR_TARGET_TEMP_STEP,
    ATTR_FAN_MODE,

    STATE_OFF,
    STATE_AUTO, STATE_HEAT, STATE_COOL, STATE_DRY, STATE_FAN_ONLY
)
import homeassistant.helpers.config_validation as cv
from homeassistant.components.discovery import SERVICE_DAIKIN
from homeassistant.helpers import discovery
from homeassistant.helpers.discovery import load_platform
from homeassistant.const import (
    CONF_HOSTS, CONF_ICON, CONF_NAME,
    CONF_MONITORED_CONDITIONS,
    TEMP_CELSIUS
)

REQUIREMENTS = ['pydaikin==0.4']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'daikin'
HTTP_RESOURCES = ['aircon/get_sensor_info', 'aircon/get_control_info']

ATTR_TARGET_TEMPERATURE = 'target_temperature'
ATTR_INSIDE_TEMPERATURE = 'inside_temperature'
ATTR_OUTSIDE_TEMPERATURE = 'outside_temperature'

# default scan interval in seconds
DEFAULT_SCAN_INTERVAL = 60

COMPONENT_TYPES = ['climate', 'sensor']

SENSOR_TYPES = {
    ATTR_INSIDE_TEMPERATURE: {
        CONF_NAME: 'Inside Temperature',
        CONF_ICON: 'mdi:thermometer'
    },
    ATTR_OUTSIDE_TEMPERATURE: {
        CONF_NAME: 'Outside Temperature',
        CONF_ICON: 'mdi:thermometer'
    }
}

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_HOSTS, default=[]): vol.Schema([cv.string]),
        vol.Optional(
            CONF_MONITORED_CONDITIONS,
            default=list(SENSOR_TYPES.keys())
        ): vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)])
    })
}, extra=vol.ALLOW_EXTRA)

HA_STATE_TO_DAIKIN = {
    STATE_FAN_ONLY: 'fan',
    STATE_DRY: 'dry',
    STATE_COOL: 'cool',
    STATE_HEAT: 'hot',
    STATE_AUTO: 'auto',
    STATE_OFF: 'off',
}

KNOWN_DEVICES = []


def setup(hass, config):
    """Establish connection with Daikin."""
    def discovery_dispatch(service, discovery_info):
        """Dispatcher for Daikin discovery events."""
        host = discovery_info.get('ip')

        if manual_device_setup(hass, host) is None:
            return

        for component in COMPONENT_TYPES:
            load_platform(hass, component, DOMAIN, discovery_info,
                          config)

    discovery.listen(hass, SERVICE_DAIKIN, discovery_dispatch)

    devices = []

    # Add static devices from the config file.
    devices.extend(
        (host, None)
        for host in config.get(DOMAIN, {}).get(CONF_HOSTS, [])
    )

    for host in devices:
        if manual_device_setup(hass, host) is not None:
            discovery_info = {
                'ip': host,
                CONF_MONITORED_CONDITIONS:
                    config.get(DOMAIN, {}).get(CONF_MONITORED_CONDITIONS)
            }
            load_platform(hass, 'sensor', DOMAIN, discovery_info, config)

    return True


def manual_device_setup(hass, host, name=None):
    """Create a Daikin instance only once."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    if hass.data[DOMAIN].get(host) is None:
        from pydaikin import appliance

        try:
            device = appliance.Appliance(host)
        except timeout:
            _LOGGER.error("Connection to Daikin could not be established")
            return False

        if name is None:
            name = device.values['name']

        hass.data[DOMAIN][host] = DaikinEntity(device, name)

    return hass.data[DOMAIN][host]


class DaikinEntity(object):
    """Keep the Daikin instance in one place and centralize the update."""

    def __init__(self, device, name):
        """Initialize the Daikin Handle."""
        from pydaikin import appliance

        self.device = device
        self.name = name
        self.ip_address = device.ip

        self.mutex = Lock()
        self._scan_interval = DEFAULT_SCAN_INTERVAL
        self._last_update = time.time()

        self._operation_list = list(
            map(str.title, set(HA_STATE_TO_DAIKIN.values()))
        )

        self._fan_list = list(
            map(str.title, appliance.daikin_values('f_rate'))
        )

        self._swing_list = list(
            map(str.title, appliance.daikin_values('f_dir'))
        )

    def get(self, key):
        """Retrieve device settings from API library cache."""
        value = None
        cast_to_float = False

        if key in [ATTR_TEMPERATURE, ATTR_INSIDE_TEMPERATURE,
                   ATTR_CURRENT_TEMPERATURE]:
            value = self.device.values.get('htemp')
            cast_to_float = True
        if key == ATTR_TARGET_TEMPERATURE:
            value = self.device.values.get('stemp')
            cast_to_float = True
        elif key == ATTR_OUTSIDE_TEMPERATURE:
            value = self.device.values.get('otemp')
            cast_to_float = True
        elif key == ATTR_FAN_MODE:
            value = self.device.represent('f_rate')[1].title()
        elif key == ATTR_SWING_MODE:
            value = self.device.represent('f_dir')[1].title()
        elif key == ATTR_TARGET_TEMP_STEP:
            return 1
        elif key == ATTR_OPERATION_MODE:
            import re

            # Daikin can return also internal states auto-1 or auto-7
            # and we need to translate them as AUTO
            value = re.sub(
                '[^a-z]',
                '',
                self.device.represent('mode')[1]
            ).title()

        if value is None:
            _LOGGER.warning("Invalid value requested for key %s", key)
        else:
            if value == "-" or value == "--":
                value = None
            elif cast_to_float:
                try:
                    value = float(value)
                except ValueError:
                    value = None

        return value

    def set(self, settings):
        """Set device settings using API."""
        values = {}

        for attr in [ATTR_TEMPERATURE, ATTR_FAN_MODE, ATTR_SWING_MODE,
                     ATTR_OPERATION_MODE, ATTR_OPERATION_MODE]:
            if attr in settings and settings[attr] is not None:

                # operation mode
                if attr == ATTR_OPERATION_MODE:
                    if settings[attr].title() in self._operation_list:
                        values['mode'] = settings[attr].lower()
                    else:
                        _LOGGER.error("Invalid operation mode %s",
                                      settings[attr])

                # swing mode
                elif attr == ATTR_FAN_MODE:
                    if settings[attr].title() in self._fan_list:
                        values['f_rate'] = settings[attr].lower()
                    else:
                        _LOGGER.error("Invalid fan mode %s",
                                      settings[attr])

                # swing mode
                elif attr == ATTR_SWING_MODE:
                    if settings[attr].title() in self._swing_list:
                        values['f_dir'] = settings[attr].lower()
                    else:
                        _LOGGER.error("Invalid swing mode %s",
                                      settings[attr])

                # temperature
                elif attr == ATTR_TEMPERATURE:
                    try:
                        values['stemp'] = str(int(settings[attr]))
                    except ValueError:
                        _LOGGER.error("Invalid temperature %s",
                                      settings[attr])

        if settings:
            self.device.set(values)
            self.update(force_refresh=True)

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self._operation_list

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def swing_list(self):
        """List of available swing modes."""
        return self._swing_list

    @property
    def fan_list(self):
        """List of available fan modes."""
        return self._fan_list

    def update(self, force_refresh=False):
        """Pull the latest data from Daikin."""
        # Acquire mutex to prevent simultaneous update from multiple threads
        with self.mutex:
            # don't update too often
            if force_refresh or \
                    (time.time() - self._last_update) >= self._scan_interval:

                try:
                    for resource in HTTP_RESOURCES:
                        self.device.values.update(
                            self.device.get_resource(resource)
                        )
                except timeout:
                    _LOGGER.warning(
                        "Connection failed for %s, retying in %d seconds",
                        self.ip_address, self._scan_interval
                    )
                    return False

                self._last_update = time.time()
