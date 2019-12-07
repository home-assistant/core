"""Support for displaying the minimal and the maximal value."""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME,
    STATE_UNKNOWN,
    STATE_UNAVAILABLE,
    ATTR_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change

_LOGGER = logging.getLogger(__name__)

ATTR_MAX_VALUE = "max_value"
ATTR_COUNT_SENSORS = "count_sensors"

ATTR_TO_PROPERTY = [ATTR_COUNT_SENSORS]

CONF_ENTITY_IDS = "entity_ids"
CONF_MAX_VALUE = "max_value"

ICON = "mdi:calculator"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_ENTITY_IDS): cv.entity_ids,
        vol.Optional(CONF_MAX_VALUE): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the binary max sensor."""
    entity_ids = config.get(CONF_ENTITY_IDS)
    name = config.get(CONF_NAME)
    max_value = config.get(CONF_MAX_VALUE)

    async_add_entities([BinaryMaxSensor(hass, entity_ids, name, max_value)], True)
    return True


class BinaryMaxSensor(Entity):
    """Representation of a binary max sensor."""

    def __init__(self, hass, entity_ids, name, max_value):
        """Initialize the binary max sensor."""
        self._hass = hass
        self._entity_ids = entity_ids
        self.last = None

        if name:
            self._name = name
        else:
            self._name = "binary max sensor".capitalize()
        if max_value:
            self._max_value = max_value
        self._unit_of_measurement = None
        self._unit_of_measurement_mismatch = False
        self.value = None
        self.count_sensors = len(self._entity_ids)
        self.states = {}

        @callback
        def async_binary_max_sensor_state_listener(entity, old_state, new_state):
            """Handle the sensor state changes."""
            if new_state.state is None or new_state.state in [
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
            ]:
                self.states[entity] = STATE_UNKNOWN
                hass.async_add_job(self.async_update_ha_state, True)
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

            self.states[entity] = new_state.state
            self.last = new_state.state

            hass.async_add_job(self.async_update_ha_state, True)

        async_track_state_change(
            hass, entity_ids, async_binary_max_sensor_state_listener
        )

    def calc_max(self, sensor_values):
        """Calculate max value, honoring unknown states.

        self._max_value, if not None, defines the greater value.
        """
        val = None
        for sval in sensor_values:
            if sval != STATE_UNKNOWN:
                if self._max_value is not None:
                    if sval == self._max_value or val is None:
                        val = sval
                else:
                    if val is None or val < sval:
                        val = sval
        return val

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._unit_of_measurement_mismatch:
            return None
        return self.value

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
            attr: getattr(self, attr)
            for attr in ATTR_TO_PROPERTY
            if getattr(self, attr) is not None
        }
        return state_attr

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    async def async_update(self):
        """Get the latest data and updates the states."""
        sensor_values = [self.states[k] for k in self._entity_ids if k in self.states]
        self.value = self.calc_max(sensor_values)
