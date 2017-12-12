"""
Monitors if a numerical sensor value is within a defined range.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.range/
"""
import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA, DEVICE_CLASSES_SCHEMA)
from homeassistant.const import (
    CONF_NAME, CONF_ENTITY_ID, STATE_UNKNOWN, ATTR_ENTITY_ID,
    CONF_DEVICE_CLASS)
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change

_LOGGER = logging.getLogger(__name__)

ATTR_SENSOR_VALUE = "sensor_value"
ATTR_POSITION = "position"
ATTR_VALUE_LOWER = "value_lower"
ATTR_VALUE_UPPER = "value_upper"
ATTR_HYSTERESIS = "hysteresis"

CONF_VALUE_LOWER = "value_lower"
CONF_VALUE_UPPER = "value_upper"
CONF_HYSTERESIS = "hysteresis"

STR_IN_RANGE = "in range"
STR_ABOVE = "above"
STR_BELOW = "below"

DEFAULT_NAME = "Range"
DEFAULT_HYSTERESIS = 0.0

POSITION_SENSOR_UNKNOWN = "sensor value unknown"
POSITION_BELOW = "below"
POSITION_IN_RANGE = "in range"
POSITION_ABOVE = "above"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Required(CONF_VALUE_LOWER): vol.Coerce(float),
    vol.Required(CONF_VALUE_UPPER): vol.Coerce(float),
    vol.Optional(
        CONF_HYSTERESIS, default=DEFAULT_HYSTERESIS): vol.Coerce(float),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Threshold sensor."""
    entity_id = config.get(CONF_ENTITY_ID)
    name = config.get(CONF_NAME)
    lower = config.get(CONF_VALUE_LOWER)
    upper = config.get(CONF_VALUE_UPPER)
    hysteresis = config.get(CONF_HYSTERESIS)
    device_class = config.get(CONF_DEVICE_CLASS)

    async_add_devices([RangeSensor(
        hass, entity_id, name, lower, upper, hysteresis, device_class)
                      ], True)

    return True


class RangeSensor(BinarySensorDevice):
    """Representation of a Range sensor."""

    def __init__(self, hass, entity_id, name, threshold_lower, threshold_upper,
                 hysteresis, device_class):
        """Initialize the Range sensor."""
        self._hass = hass
        self._entity_id = entity_id
        self._name = name

        self._threshold_lower = threshold_lower
        self._threshold_upper = threshold_upper
        self._hysteresis = hysteresis

        self._device_class = device_class

        self._state = None
        self.sensor_value = None

        @callback
        # pylint: disable=invalid-name
        def async_threshold_sensor_state_listener(
                entity, old_state, new_state):
            """Handle sensor state changes."""
            try:
                self.sensor_value = None if new_state.state == STATE_UNKNOWN \
                    else float(new_state.state)
            except (ValueError, TypeError):
                self.sensor_value = None
                _LOGGER.warning("State is not numerical")

            hass.async_add_job(self.async_update_ha_state, True)

        async_track_state_change(
            hass, entity_id, async_threshold_sensor_state_listener)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state == POSITION_IN_RANGE

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_class(self):
        """Return the sensor class of the sensor."""
        return self._device_class

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_ENTITY_ID: self._entity_id,
            ATTR_SENSOR_VALUE: self.sensor_value,
            ATTR_POSITION: self._state,
            ATTR_VALUE_LOWER: self._threshold_lower,
            ATTR_VALUE_UPPER: self._threshold_upper,
            ATTR_HYSTERESIS: self._hysteresis
        }

    @asyncio.coroutine
    def async_update(self):
        """Get the latest data and updates the states."""
        if self.sensor_value is None:
            self._state = POSITION_SENSOR_UNKNOWN
        elif self.sensor_value < (self._threshold_lower - self._hysteresis):
            self._state = POSITION_BELOW
        elif self.sensor_value > (self._threshold_upper + self._hysteresis):
            self._state = POSITION_ABOVE
        elif self.sensor_value > (self._threshold_lower + self._hysteresis) \
                and self.sensor_value < \
                (self._threshold_upper - self._hysteresis):
            self._state = POSITION_IN_RANGE
