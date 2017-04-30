"""
Support for Zehnder ComfoConnect bridges.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/fan.comfoconnect/
"""
import logging
import time

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.fan import (
    FanEntity, PLATFORM_SCHEMA, ATTR_SPEED,
    SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH,
    SUPPORT_SET_SPEED)
from homeassistant.const import (
    CONF_HOST, CONF_TOKEN, CONF_PIN, CONF_NAME)

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = [
    'https://github.com/michaelarnauts/comfoconnect'
    '/archive/0.1.zip#pycomfoconnect==0.1']

ATTR_CURRENT_TEMPERATURE = 'current_temperature'
ATTR_CURRENT_HUMIDITY = 'current_humidity'
ATTR_OUTSIDE_TEMPERATURE = 'outside_temperature'
ATTR_OUTSIDE_HUMIDITY = 'outside_humidity'
ATTR_AIR_FLOW_SUPPLY = 'air_flow_supply'
ATTR_AIR_FLOW_EXTRACT = 'air_flow_extract'

CONF_USER_AGENT = 'user_agent'

DEFAULT_PIN = 0
DEFAULT_TOKEN = '00000000000000000000000000000001'
DEFAULT_NAME = 'ComfoAirQ'
DEFAULT_USER_AGENT = 'Home Assistant'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_TOKEN, default=DEFAULT_TOKEN):
        vol.Length(min=32, max=32, msg='invalid token'),
    vol.Optional(CONF_USER_AGENT, default=DEFAULT_USER_AGENT):
        cv.string,
    vol.Optional(CONF_PIN, default=DEFAULT_PIN): cv.positive_int,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the ComfoConnect bridge."""
    from pycomfoconnect import (Bridge)

    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    token = config.get(CONF_TOKEN)
    user_agent = config.get(CONF_USER_AGENT)
    pin = config.get(CONF_PIN)

    # Run discovery on the configured ip
    bridges = Bridge.discover(host)
    if not bridges:
        _LOGGER.error('Could not connect to ComfoConnect bridge on %s', host)
        return False

    for bridge in bridges:
        _LOGGER.info('Bridge found: %s (%s)', bridge.remote_uuid.hex(),
                     bridge.ip)
        add_devices([
            ComfoConnectBridge(name, bridge, token, user_agent, pin)
        ], True)

    return


class ComfoConnectBridge(FanEntity):
    """Representation of a ComfoConnect bridge."""

    def __init__(self, name, bridge, token, friendly_name, pin):
        """Initialize the ComfoConnect bridge."""
        from pycomfoconnect import (
            ComfoConnect, SENSOR_FAN_SPEED_MODE, SENSOR_TEMPERATURE_EXTRACT,
            SENSOR_TEMPERATURE_OUTDOOR, SENSOR_HUMIDITY_EXTRACT,
            SENSOR_HUMIDITY_OUTDOOR, SENSOR_FAN_SUPPLY_FLOW,
            SENSOR_FAN_EXHAUST_FLOW
        )

        self._name = name
        self._comfoconnect = ComfoConnect(bridge, self.sensor_callback)
        self._token = bytes.fromhex(token)
        self._friendly_name = friendly_name
        self._pin = pin
        self._data = {}
        self._fresh_data = {}

        self._subscribed_sensors = [
            SENSOR_FAN_SPEED_MODE,
            SENSOR_FAN_SUPPLY_FLOW,
            SENSOR_FAN_EXHAUST_FLOW,
            SENSOR_TEMPERATURE_EXTRACT,
            SENSOR_TEMPERATURE_OUTDOOR,
            SENSOR_HUMIDITY_EXTRACT,
            SENSOR_HUMIDITY_OUTDOOR,
        ]

    @property
    def name(self):
        """Return the name of the bridge."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return 'mdi:air-conditioner'

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_SET_SPEED

    @property
    def speed(self):
        """Return the current fan mode."""
        if ATTR_SPEED in self._data:
            return self._data[ATTR_SPEED]

    @property
    def speed_list(self):
        """List of available fan modes."""
        return [SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

    def turn_on(self, speed: str=None, **kwargs) -> None:
        """Turn on the entity."""
        if speed is None:
            speed = SPEED_LOW
        self.set_speed(speed)

    def turn_off(self) -> None:
        """Turn off the entity."""
        self.set_speed(SPEED_OFF)

    def set_speed(self, mode):
        """Set fan speed."""
        from pycomfoconnect.error import (
            PyComfoConnectOtherSession, PyComfoConnectNotAllowed)
        from pycomfoconnect.const import (
            FAN_MODE_AWAY, FAN_MODE_LOW, FAN_MODE_MEDIUM,
            FAN_MODE_HIGH
        )

        _LOGGER.debug('Changing fan mode to %s...' % mode)
        try:
            self._comfoconnect.connect(
                self._token, self._friendly_name, self._pin)
            _LOGGER.debug('Connected to bridge.')

            if mode == SPEED_OFF:
                self._comfoconnect.set_fan_mode(FAN_MODE_AWAY)
            elif mode == SPEED_LOW:
                self._comfoconnect.set_fan_mode(FAN_MODE_LOW)
            elif mode == SPEED_MEDIUM:
                self._comfoconnect.set_fan_mode(FAN_MODE_MEDIUM)
            elif mode == SPEED_HIGH:
                self._comfoconnect.set_fan_mode(FAN_MODE_HIGH)

            # Update current mode
            self._data[ATTR_SPEED] = mode
            self.schedule_update_ha_state()

        except PyComfoConnectOtherSession as ex:
            _LOGGER.error('Another session with "%s" is active.',
                          ex.devicename)

        except PyComfoConnectNotAllowed:
            _LOGGER.error('Could not register. Invalid PIN!')

        finally:
            self._comfoconnect.disconnect()
            _LOGGER.debug('Disconnected from bridge.')

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        from pycomfoconnect import (
            SENSOR_FAN_SPEED_MODE, SENSOR_FAN_SUPPLY_FLOW,
            SENSOR_FAN_EXHAUST_FLOW, SENSOR_TEMPERATURE_EXTRACT,
            SENSOR_TEMPERATURE_OUTDOOR, SENSOR_HUMIDITY_EXTRACT,
            SENSOR_HUMIDITY_OUTDOOR
        )

        data = {}

        for key, value in self._data.items():
            if key == SENSOR_FAN_SPEED_MODE:
                if value == 0:
                    data[ATTR_SPEED] = SPEED_OFF
                elif value == 1:
                    data[ATTR_SPEED] = SPEED_LOW
                elif value == 2:
                    data[ATTR_SPEED] = SPEED_MEDIUM
                elif value == 3:
                    data[ATTR_SPEED] = SPEED_HIGH

            elif key == SENSOR_HUMIDITY_EXTRACT:
                data[ATTR_CURRENT_HUMIDITY] = value

            elif key == SENSOR_HUMIDITY_OUTDOOR:
                data[ATTR_OUTSIDE_HUMIDITY] = value

            elif key == SENSOR_TEMPERATURE_EXTRACT:
                data[ATTR_CURRENT_TEMPERATURE] = value / 10.0

            elif key == SENSOR_TEMPERATURE_OUTDOOR:
                data[ATTR_OUTSIDE_TEMPERATURE] = value / 10.0

            elif key == SENSOR_FAN_SUPPLY_FLOW:
                data[ATTR_AIR_FLOW_SUPPLY] = value

            elif key == SENSOR_FAN_EXHAUST_FLOW:
                data[ATTR_AIR_FLOW_EXTRACT] = value

        return data

    def update(self):
        """Open connection to the Bridge."""
        from pycomfoconnect.error import (
            PyComfoConnectOtherSession, PyComfoConnectNotAllowed)

        _LOGGER.debug('Updating sensor data...')
        try:
            self._comfoconnect.connect(
                self._token, self._friendly_name, self._pin)
            _LOGGER.debug('Connected to bridge.')

            # Clean sensor data
            self._fresh_data = {}

            # Subscribe to sensor values.
            for sensor in self._subscribed_sensors:
                self._comfoconnect.request(sensor)
            _LOGGER.debug('Subscribed to sensors.')

            # Wait maximum of 5 seconds for all the sensor values.
            self.wait_for_sensor_values(5)
            _LOGGER.debug('Sensor data received.')

            # Update data with new values
            self._data.update(self._fresh_data)

        except PyComfoConnectOtherSession as ex:
            _LOGGER.error('Another session with "%s" is active.',
                          ex.devicename)

        except PyComfoConnectNotAllowed:
            _LOGGER.error('Could not register. Invalid PIN!')

        finally:
            self._comfoconnect.disconnect()
            _LOGGER.debug('Disconnected from bridge.')

    def wait_for_sensor_values(self, max_seconds):
        """Wait for all the sensor values to have arrived."""
        deadline = time.time() + max_seconds
        for sensor in self._subscribed_sensors:
            if sensor in self._fresh_data:
                continue

            if time.time() > deadline:
                _LOGGER.error('Timeout while waiting for sensor data.')
                return

            time.sleep(1)

    def sensor_callback(self, var, value):
        """Callback function for sensor updates."""
        _LOGGER.debug('Got value from bridge: %d = %d', var, value)
        self._fresh_data[var] = value
