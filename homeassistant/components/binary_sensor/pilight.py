"""
Support for Pilight binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.pilight/
"""
import logging
import datetime
import homeassistant.util.dt as dt_util

import voluptuous as vol

from homeassistant.const import (
    CONF_NAME,
    CONF_DISARM_AFTER_TRIGGER,
    CONF_PAYLOAD,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    STATE_ON,
    STATE_OFF)
from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA,
    BinarySensorDevice)
from homeassistant.helpers.event import track_point_in_time
import homeassistant.components.pilight as pilight
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_VARIABLE = 'variable'

DEFAULT_NAME = 'Pilight Binary Sensor'
DEPENDENCIES = ['pilight']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_VARIABLE): cv.string,
    vol.Required(CONF_PAYLOAD): vol.Schema(dict),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PAYLOAD_ON, default='on'): cv.string,
    vol.Optional(CONF_PAYLOAD_OFF, default='off'): cv.string,
    vol.Optional(CONF_DISARM_AFTER_TRIGGER, default='no'): cv.string
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Pilight Binary Sensor."""
    disarm = config.get(CONF_DISARM_AFTER_TRIGGER)
    if disarm == 'yes':
        add_devices([PilightTriggerSensor(
            hass=hass,
            name=config.get(CONF_NAME),
            variable=config.get(CONF_VARIABLE),
            payload=config.get(CONF_PAYLOAD),
            on_value=config.get(CONF_PAYLOAD_ON),
            off_value=config.get(CONF_PAYLOAD_OFF),
        )])
    else:
        add_devices([PilightBinarySensor(
            hass=hass,
            name=config.get(CONF_NAME),
            variable=config.get(CONF_VARIABLE),
            payload=config.get(CONF_PAYLOAD),
            on_value=config.get(CONF_PAYLOAD_ON),
            off_value=config.get(CONF_PAYLOAD_OFF),
        )])


class PilightBinarySensor(BinarySensorDevice):
    """Representation of a binary sensor that can be updated using Pilight."""

    def __init__(self, hass, name, variable, payload, on_value, off_value):
        """Initialize the sensor."""
        self._state = False
        self._hass = hass
        self._name = name
        self._variable = variable
        self._payload = payload
        self._on_value = on_value
        self._off_value = off_value

        hass.bus.listen(pilight.EVENT, self._handle_code)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._state

    @property
    def state(self):
        """Return the state of the entity."""
        return STATE_ON if self._state else STATE_OFF

    def _handle_code(self, call):
        """Handle received code by the pilight-daemon.

        If the code matches the defined playload
        of this sensor the sensor state is changed accordingly.
        """
        # Check if received code matches defined playoad
        # True if payload is contained in received code dict, not
        # all items have to match
        if self._payload.items() <= call.data.items():
            try:
                value = call.data[self._variable]
                self._state = (value == self._on_value)
                self.schedule_update_ha_state()
            except KeyError:
                _LOGGER.error(
                    'No variable %s in received code data %s',
                    str(self._variable), str(call.data))


class PilightTriggerSensor(BinarySensorDevice):
    """Representation of a binary sensor that can be updated using Pilight."""

    def __init__(
            self,
            hass,
            name,
            variable,
            payload,
            on_value,
            off_value,
            rst_dly_sec=30):
        """Initialize the sensor."""
        self._state = False
        self._hass = hass
        self._name = name
        self._variable = variable
        self._payload = payload
        self._on_value = on_value
        self._off_value = off_value
        self._reset_delay_sec = rst_dly_sec
        self._delay_after = None
        self._hass = hass

        hass.bus.listen(pilight.EVENT, self._handle_code)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._state

    @property
    def state(self):
        """Return the state of the entity."""
        return STATE_ON if self._state else STATE_OFF

    def _reset_state(self, call):
        self._state = False
        self.schedule_update_ha_state()

    def _handle_code(self, call):
        """Handle received code by the pilight-daemon.

        If the code matches the defined playload
        of this sensor the sensor state is changed accordingly.
        """
        # Check if received code matches defined playoad
        # True if payload is contained in received code dict, not
        # all items have to match
        if self._payload.items() <= call.data.items():
            try:
                value = call.data[self._variable]
                self._state = (value == self._on_value)
                self._delay_after = dt_util.utcnow() + datetime.timedelta(
                    seconds=self._reset_delay_sec)
                track_point_in_time(
                    self._hass, self._reset_state,
                    self._delay_after)
                self.schedule_update_ha_state()
            except KeyError:
                _LOGGER.error(
                    'No variable %s in received code data %s',
                    str(self._variable), str(call.data))
