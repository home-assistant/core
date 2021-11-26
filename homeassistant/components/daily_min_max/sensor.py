"""Support for displaying min or max value of a sensor(s) throught a period of a day"""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    CONF_TYPE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_change
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from . import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

ATTR_MIN_VALUE = "min_value"
ATTR_MIN_ENTITY_ID = "min_entity_id"
ATTR_MAX_VALUE = "max_value"
ATTR_MAX_ENTITY_ID = "max_entity_id"
ATTR_COUNT_SENSORS = "count_sensors"
ATTR_LAST = "last"
ATTR_LAST_ENTITY_ID = "last_entity_id"

ATTR_TO_PROPERTY = [
    ATTR_COUNT_SENSORS,
    ATTR_MAX_VALUE,
    ATTR_MAX_ENTITY_ID,
    ATTR_MIN_VALUE,
    ATTR_MIN_ENTITY_ID,
    ATTR_LAST,
    ATTR_LAST_ENTITY_ID,
]

CONF_ENTITY_IDS = "entity_ids"
CONF_ROUND_DIGITS = "round_digits"
CONF_TIME = "time"

ICON = "mdi:calculator"

SENSOR_TYPES = {
    ATTR_MIN_VALUE: "min",
    ATTR_MAX_VALUE: "max",
}


def valid_time(conf):
    time = conf.get(CONF_TIME)
    parsed_time = dt_util.parse_time(time)
    if parsed_time is not None:
        return conf
    raise vol.Invalid(f"Time value '{time}' can't be parsed as a time")


PLATFORM_SCHEMA = vol.All(
    PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_TYPE, default=SENSOR_TYPES[ATTR_MAX_VALUE]): vol.All(
                cv.string, vol.In(SENSOR_TYPES.values())
            ),
            vol.Optional(CONF_NAME): cv.string,
            vol.Required(CONF_ENTITY_IDS): cv.entity_ids,
            vol.Optional(CONF_ROUND_DIGITS, default=2): vol.Coerce(int),
            vol.Optional(CONF_TIME, default="00:00:00"): cv.string
        }
    ),
    valid_time
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the min/max sensor."""
    entity_ids = config.get(CONF_ENTITY_IDS)
    name = config.get(CONF_NAME)
    sensor_type = config.get(CONF_TYPE)
    round_digits = config.get(CONF_ROUND_DIGITS)
    time = config.get(CONF_TIME)

    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)

    async_add_entities(
        [DailyMinMaxSensor(entity_ids, name, sensor_type, round_digits, time)])


def calc_min(sensor_values):
    """Calculate min value, honoring unknown states."""
    val = None
    entity_id = None
    for sensor_id, sensor_value in sensor_values:
        if sensor_value not in [STATE_UNKNOWN, STATE_UNAVAILABLE] and (
            val is None or val > sensor_value
        ):
            entity_id, val = sensor_id, sensor_value
    return entity_id, val


def calc_max(sensor_values):
    """Calculate max value, honoring unknown states."""
    val = None
    entity_id = None
    for sensor_id, sensor_value in sensor_values:
        if sensor_value not in [STATE_UNKNOWN, STATE_UNAVAILABLE] and (
            val is None or val < sensor_value
        ):
            entity_id, val = sensor_id, sensor_value
    return entity_id, val


class DailyMinMaxSensor(RestoreEntity, SensorEntity):

    def __init__(self, entity_ids, name, sensor_type, round_digits, time):
        self._entity_ids = entity_ids
        self._sensor_type = sensor_type
        self._time = dt_util.parse_time(time)
        self._round_digits = round_digits

        if name:
            self._name = name
        else:
            self._name = f"{next(v for k, v in SENSOR_TYPES.items() if self._sensor_type == v)} sensor".capitalize(
            )
        self._unit_of_measurement = None
        self._unit_of_measurement_mismatch = False
        self.min_value = self.max_value = None
        self.min_entity_id = self.max_entity_id = self.last_entity_id = None
        self.count_sensors = len(self._entity_ids)
        self.states = {}
        self.last = None

    async def async_added_to_hass(self):
        """Handle added to Hass."""
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._entity_ids, self._async_sensor_state_listener
            )
        )

        self.async_on_remove(
            async_track_time_change(
                self.hass, self.reset, hour=[self._time.hour], minute=[self._time.minute], second=[self._time.second]
            )
        )

        if last_state := await self.async_get_last_state():
            self._state = last_state.state
            self._attrs = last_state.attributes
            self._available = True

            # Don't know if all this is necessary
            if self._attrs:
                self.max_entity_id = self._attrs['max_entity_id']
                self.max_value = self._attrs['max_value']
                self.min_entity_id = self._attrs['min_entity_id']
                self.min_value = self._attrs['min_value']
                self.last_entity_id = self._attrs['last_entity_id']
                self.last = self._attrs['last']

        self._calc_values()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self._unit_of_measurement_mismatch:
            return None
        return getattr(
            self, next(k for k, v in SENSOR_TYPES.items()
                       if self._sensor_type == v)
        )

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        if self._unit_of_measurement_mismatch:
            return "ERR"
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            attr: getattr(self, attr)
            for attr in ATTR_TO_PROPERTY
            if getattr(self, attr) is not None
        }

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    @callback
    def _async_sensor_state_listener(self, event):
        """Handle the sensor state changes."""
        new_state = event.data.get("new_state")
        entity = event.data.get("entity_id")

        if new_state.state is None or new_state.state in [
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ]:
            self.states[entity] = STATE_UNKNOWN
            self._calc_values()
            self.async_write_ha_state()
            return

        if self._unit_of_measurement is None:
            self._unit_of_measurement = new_state.attributes.get(
                ATTR_UNIT_OF_MEASUREMENT
            )

        if self._unit_of_measurement != new_state.attributes.get(
            ATTR_UNIT_OF_MEASUREMENT
        ):
            _LOGGER.warning(
                "Units of measurement do not match for entity %s", self.entity_id
            )
            self._unit_of_measurement_mismatch = True

        try:
            self.states[entity] = float(new_state.state)
            self.last = float(new_state.state)
            self.last_entity_id = entity
        except ValueError:
            _LOGGER.warning(
                "Unable to store state. Only numerical states are supported"
            )

        self._calc_values()
        self.async_write_ha_state()

    @callback
    def _calc_values(self):
        """Calculate the values."""
        sensor_values = [
            (entity_id, self.states[entity_id])
            for entity_id in self._entity_ids
            if entity_id in self.states
        ]
        current_min_entity_id, current_min_value = calc_min(sensor_values)
        if current_min_value is not None:
            if self.min_value is None or current_min_value < self.min_value:
                self.min_entity_id, self.min_value = current_min_entity_id, current_min_value
        current_max_entity_id, current_max_value = calc_max(sensor_values)
        if current_max_value is not None:
            if self.max_value is None or current_max_value > self.max_value:
                self.max_entity_id, self.max_value = current_max_entity_id, current_max_value

    @callback
    def reset(self, now):
        self.min_value = self.max_value = self.last
        self.min_entity_id = self.max_entity_id = self.last_entity_id = None
        self.async_write_ha_state()


