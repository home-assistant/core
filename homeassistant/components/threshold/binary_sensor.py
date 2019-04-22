"""Support for monitoring if a sensor value is below/above a threshold."""
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA, PLATFORM_SCHEMA, BinarySensorDevice)
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_DEVICE_CLASS, CONF_ENTITY_ID, CONF_NAME,
    STATE_UNKNOWN)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_state_change

_LOGGER = logging.getLogger(__name__)

ATTR_HYSTERESIS = 'hysteresis'
ATTR_LOWER = 'lower'
ATTR_POSITION = 'position'
ATTR_SENSOR_VALUE = 'sensor_value'
ATTR_TYPE = 'type'
ATTR_UPPER = 'upper'

CONF_HYSTERESIS = 'hysteresis'
CONF_LOWER = 'lower'
CONF_UPPER = 'upper'

DEFAULT_NAME = 'Threshold'
DEFAULT_HYSTERESIS = 0.0

POSITION_ABOVE = 'above'
POSITION_BELOW = 'below'
POSITION_IN_RANGE = 'in_range'
POSITION_UNKNOWN = 'unknown'

TYPE_LOWER = 'lower'
TYPE_RANGE = 'range'
TYPE_UPPER = 'upper'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_HYSTERESIS, default=DEFAULT_HYSTERESIS):
        vol.Coerce(float),
    vol.Optional(CONF_LOWER): vol.Coerce(float),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_UPPER): vol.Coerce(float),
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Threshold sensor."""
    entity_id = config.get(CONF_ENTITY_ID)
    name = config.get(CONF_NAME)
    lower = config.get(CONF_LOWER)
    upper = config.get(CONF_UPPER)
    hysteresis = config.get(CONF_HYSTERESIS)
    device_class = config.get(CONF_DEVICE_CLASS)

    async_add_entities([ThresholdSensor(
        hass, entity_id, name, lower, upper, hysteresis, device_class)], True)


class ThresholdSensor(BinarySensorDevice):
    """Representation of a Threshold sensor."""

    def __init__(self, hass, entity_id, name, lower, upper, hysteresis,
                 device_class):
        """Initialize the Threshold sensor."""
        self._hass = hass
        self._entity_id = entity_id
        self._name = name
        self._threshold_lower = lower
        self._threshold_upper = upper
        self._hysteresis = hysteresis
        self._device_class = device_class

        self._state_position = None
        self._state = False
        self.sensor_value = None

        @callback
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
        return self._state

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_class(self):
        """Return the sensor class of the sensor."""
        return self._device_class

    @property
    def threshold_type(self):
        """Return the type of threshold this sensor represents."""
        if self._threshold_lower is not None and \
                self._threshold_upper is not None:
            return TYPE_RANGE
        if self._threshold_lower is not None:
            return TYPE_LOWER
        if self._threshold_upper is not None:
            return TYPE_UPPER

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_ENTITY_ID: self._entity_id,
            ATTR_HYSTERESIS: self._hysteresis,
            ATTR_LOWER: self._threshold_lower,
            ATTR_POSITION: self._state_position,
            ATTR_SENSOR_VALUE: self.sensor_value,
            ATTR_TYPE: self.threshold_type,
            ATTR_UPPER: self._threshold_upper,
        }

    async def async_update(self):
        """Get the latest data and updates the states."""
        def below(threshold):
            """Determine if the sensor value is below a threshold."""
            return self.sensor_value < (threshold - self._hysteresis)

        def above(threshold):
            """Determine if the sensor value is above a threshold."""
            return self.sensor_value > (threshold + self._hysteresis)

        if self.sensor_value is None:
            self._state_position = POSITION_UNKNOWN
            self._state = False

        elif self.threshold_type == TYPE_LOWER:
            if below(self._threshold_lower):
                self._state_position = POSITION_BELOW
                self._state = True
            elif above(self._threshold_lower):
                self._state_position = POSITION_ABOVE
                self._state = False

        elif self.threshold_type == TYPE_UPPER:
            if above(self._threshold_upper):
                self._state_position = POSITION_ABOVE
                self._state = True
            elif below(self._threshold_upper):
                self._state_position = POSITION_BELOW
                self._state = False

        elif self.threshold_type == TYPE_RANGE:
            if below(self._threshold_lower):
                self._state_position = POSITION_BELOW
                self._state = False
            if above(self._threshold_upper):
                self._state_position = POSITION_ABOVE
                self._state = False
            elif above(self._threshold_lower) and below(self._threshold_upper):
                self._state_position = POSITION_IN_RANGE
                self._state = True
