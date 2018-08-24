"""
Support for displaying the minimal and the maximal value.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.min_max/
"""
import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, STATE_UNKNOWN, CONF_TYPE, ATTR_UNIT_OF_MEASUREMENT)
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change

_LOGGER = logging.getLogger(__name__)

ATTR_MIN_VALUE = 'min_value'
ATTR_MAX_VALUE = 'max_value'
ATTR_COUNT_SENSORS = 'count_sensors'
ATTR_MEAN = 'mean'
ATTR_LAST = 'last'

ATTR_TO_PROPERTY = [
    ATTR_COUNT_SENSORS,
    ATTR_MAX_VALUE,
    ATTR_MEAN,
    ATTR_MIN_VALUE,
    ATTR_LAST,
]

CONF_ENTITY_IDS = 'entity_ids'
CONF_ROUND_DIGITS = 'round_digits'

ICON = 'mdi:calculator'

SENSOR_TYPES = {
    ATTR_MIN_VALUE: 'min',
    ATTR_MAX_VALUE: 'max',
    ATTR_MEAN: 'mean',
    ATTR_LAST: 'last',
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_TYPE, default=SENSOR_TYPES[ATTR_MAX_VALUE]):
        vol.All(cv.string, vol.In(SENSOR_TYPES.values())),
    vol.Optional(CONF_NAME): cv.string,
    vol.Required(CONF_ENTITY_IDS): cv.entity_ids,
    vol.Optional(CONF_ROUND_DIGITS, default=2): vol.Coerce(int),
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_entities,
                         discovery_info=None):
    """Set up the min/max/mean sensor."""
    entity_ids = config.get(CONF_ENTITY_IDS)
    name = config.get(CONF_NAME)
    sensor_type = config.get(CONF_TYPE)
    round_digits = config.get(CONF_ROUND_DIGITS)

    async_add_entities(
        [MinMaxSensor(hass, entity_ids, name, sensor_type, round_digits)],
        True)
    return True


def calc_min(sensor_values):
    """Calculate min value, honoring unknown states."""
    val = STATE_UNKNOWN
    for sval in sensor_values:
        if sval != STATE_UNKNOWN:
            if val == STATE_UNKNOWN or val > sval:
                val = sval
    return val


def calc_max(sensor_values):
    """Calculate max value, honoring unknown states."""
    val = STATE_UNKNOWN
    for sval in sensor_values:
        if sval != STATE_UNKNOWN:
            if val == STATE_UNKNOWN or val < sval:
                val = sval
    return val


def calc_mean(sensor_values, round_digits):
    """Calculate mean value, honoring unknown states."""
    val = 0
    count = 0
    for sval in sensor_values:
        if sval != STATE_UNKNOWN:
            val += sval
            count += 1
    if count == 0:
        return STATE_UNKNOWN
    return round(val/count, round_digits)


class MinMaxSensor(Entity):
    """Representation of a min/max sensor."""

    def __init__(self, hass, entity_ids, name, sensor_type, round_digits):
        """Initialize the min/max sensor."""
        self._hass = hass
        self._entity_ids = entity_ids
        self._sensor_type = sensor_type
        self._round_digits = round_digits

        if name:
            self._name = name
        else:
            self._name = '{} sensor'.format(
                next(v for k, v in SENSOR_TYPES.items()
                     if self._sensor_type == v)).capitalize()
        self._unit_of_measurement = None
        self._unit_of_measurement_mismatch = False
        self.min_value = self.max_value = self.mean = self.last = STATE_UNKNOWN
        self.count_sensors = len(self._entity_ids)
        self.states = {}

        @callback
        def async_min_max_sensor_state_listener(entity, old_state, new_state):
            """Handle the sensor state changes."""
            if new_state.state is None or new_state.state in STATE_UNKNOWN:
                self.states[entity] = STATE_UNKNOWN
                hass.async_add_job(self.async_update_ha_state, True)
                return

            if self._unit_of_measurement is None:
                self._unit_of_measurement = new_state.attributes.get(
                    ATTR_UNIT_OF_MEASUREMENT)

            if self._unit_of_measurement != new_state.attributes.get(
                    ATTR_UNIT_OF_MEASUREMENT):
                _LOGGER.warning(
                    "Units of measurement do not match for entity %s",
                    self.entity_id)
                self._unit_of_measurement_mismatch = True

            try:
                self.states[entity] = float(new_state.state)
                self.last = float(new_state.state)
            except ValueError:
                _LOGGER.warning("Unable to store state. "
                                "Only numerical states are supported")

            hass.async_add_job(self.async_update_ha_state, True)

        async_track_state_change(
            hass, entity_ids, async_min_max_sensor_state_listener)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._unit_of_measurement_mismatch:
            return STATE_UNKNOWN
        return getattr(self, next(
            k for k, v in SENSOR_TYPES.items() if self._sensor_type == v))

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        if self._unit_of_measurement_mismatch:
            return "ERR"
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        state_attr = {
            attr: getattr(self, attr) for attr
            in ATTR_TO_PROPERTY if getattr(self, attr) is not None
        }
        return state_attr

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    @asyncio.coroutine
    def async_update(self):
        """Get the latest data and updates the states."""
        sensor_values = [self.states[k] for k in self._entity_ids
                         if k in self.states]
        self.min_value = calc_min(sensor_values)
        self.max_value = calc_max(sensor_values)
        self.mean = calc_mean(sensor_values, self._round_digits)
