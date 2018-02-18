"""
Support for displaying the minimal and the maximal value.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.min_max/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.sensor import ENTITY_ID_FORMAT, PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_SENSORS, CONF_FRIENDLY_NAME, CONF_TYPE,
    ATTR_UNIT_OF_MEASUREMENT, STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity, async_generate_entity_id
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

ICON = 'mdi:calculator'

SENSOR_TYPES = {
    ATTR_MIN_VALUE: 'min',
    ATTR_MAX_VALUE: 'max',
    ATTR_MEAN: 'mean',
    ATTR_LAST: 'last',
}

CONF_ENTITY_IDS = 'entity_ids'
CONF_ROUND_DIGITS = 'round_digits'

SENSOR_SCHEMA = vol.Schema({
    vol.Optional(CONF_TYPE, default=SENSOR_TYPES[ATTR_MAX_VALUE]):
        vol.All(cv.string, vol.In(SENSOR_TYPES.values())),
    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
    vol.Required(CONF_ENTITY_IDS): cv.entity_ids,
    vol.Optional(CONF_ROUND_DIGITS, default=2): vol.Coerce(int),
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENSORS): vol.Schema({cv.slug: SENSOR_SCHEMA})
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the min/max/mean sensor."""
    sensors = []

    for device, device_config in config[CONF_SENSORS].items():
        entity_ids = device_config.get(CONF_ENTITY_IDS)
        friendly_name = device_config.get(CONF_FRIENDLY_NAME, device)
        sensor_type = device_config.get(CONF_TYPE)
        round_digits = device_config.get(CONF_ROUND_DIGITS)
        sensors.append(
            MinMaxSensor(hass, device, entity_ids, friendly_name,
                         sensor_type, round_digits))

    if not sensors:
        _LOGGER.error("No min_max sensors added.")
        return False

    async_add_devices(sensors, True)
    return True


def calc_min(sensor_values):
    """Calculate min value, honoring unknown states."""
    val = STATE_UNKNOWN
    for sval in sensor_values:
        if sval == STATE_UNKNOWN:
            continue
        if val == STATE_UNKNOWN or val > sval:
            val = sval
    return val


def calc_max(sensor_values):
    """Calculate max value, honoring unknown states."""
    val = STATE_UNKNOWN
    for sval in sensor_values:
        if sval == STATE_UNKNOWN:
            continue
        if val == STATE_UNKNOWN or val < sval:
            val = sval
    return val


def calc_mean(sensor_values, round_digits):
    """Calculate mean value, honoring unknown states."""
    val = 0
    count = 0
    for sval in sensor_values:
        if sval == STATE_UNKNOWN:
            continue
        val += sval
        count += 1
    if count == 0:
        return STATE_UNKNOWN
    return round(val/count, round_digits)


class MinMaxSensor(Entity):
    """Representation of a min/max sensor."""

    def __init__(self, hass, device_id, entity_ids, friendly_name,
                 sensor_type, round_digits):
        """Initialize the min/max sensor."""
        self._hass = hass
        self._name = friendly_name
        self._entity_ids = entity_ids
        self._sensor_type = sensor_type
        self._round_digits = round_digits
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass)

        self._unit_of_measurement = None
        self._unit_of_measurement_mismatch = False
        self.min_value = self.max_value = self.mean = self.last = STATE_UNKNOWN
        self.count_sensors = len(self._entity_ids)
        self.states = {}

        @callback
        # pylint: disable=invalid-name
        def async_min_max_sensor_state_listener(entity, old_state, new_state):
            """Handle the sensor state changes."""
            if new_state.state is None or new_state.state in STATE_UNKNOWN:
                self.states[entity] = STATE_UNKNOWN
                hass.async_add_job(self.async_update_ha_state, True)
                return

            new_unit = new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            if self._unit_of_measurement is None:
                self._unit_of_measurement = new_unit

            if self._unit_of_measurement != new_unit:
                _LOGGER.warning(
                    "Units of measurement do not match for entity %s",
                    self.entity_id)
                self._unit_of_measurement_mismatch = True

            try:
                self.states[entity] = float(new_state.state)
                self.last = float(new_state.state)
            except ValueError:
                _LOGGER.warning("Unable to store state. "
                                "Only numerical states are supported.")

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
