"""Support for displaying minimal, maximal, mean or median values."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    CONF_TYPE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    ATTR_MAX_VALUE,
    ATTR_TO_PROPERTY,
    CONF_ENTITY_IDS,
    CONF_ROUND_DIGITS,
    DOMAIN,
    ICON,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_TYPE, default=SENSOR_TYPES[ATTR_MAX_VALUE]): vol.All(
            cv.string, vol.In(SENSOR_TYPES.values())
        ),
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_ENTITY_IDS): cv.entity_ids,
        vol.Optional(CONF_ROUND_DIGITS, default=2): vol.Coerce(int),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the min/max/mean sensor."""
    _LOGGER.warning(
        "Your Min/Max configuration has been imported into the UI; "
        "please remove it from configuration.yaml as support for it "
        "will be removed in a future release"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the min/max/mean sensor."""
    async_add_entities([MinMaxSensor(config_entry)])


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


def calc_mean(sensor_values, round_digits):
    """Calculate mean value, honoring unknown states."""
    result = [
        sensor_value
        for _, sensor_value in sensor_values
        if sensor_value not in [STATE_UNKNOWN, STATE_UNAVAILABLE]
    ]

    if not result:
        return None
    return round(sum(result) / len(result), round_digits)


def calc_median(sensor_values, round_digits):
    """Calculate median value, honoring unknown states."""
    result = [
        sensor_value
        for _, sensor_value in sensor_values
        if sensor_value not in [STATE_UNKNOWN, STATE_UNAVAILABLE]
    ]

    if not result:
        return None
    result.sort()
    if len(result) % 2 == 0:
        median1 = result[len(result) // 2]
        median2 = result[len(result) // 2 - 1]
        median = (median1 + median2) / 2
    else:
        median = result[len(result) // 2]
    return round(median, round_digits)


class MinMaxSensor(SensorEntity):
    """Representation of a min/max sensor."""

    def __init__(self, config_entry):
        """Initialize the min/max sensor."""
        self._config_entry = config_entry
        self._entity_ids = config_entry.data[CONF_ENTITY_IDS]
        self._sensor_type = config_entry.data[CONF_TYPE]
        self._round_digits = config_entry.data[CONF_ROUND_DIGITS]

        self._unit_of_measurement = None
        self._unit_of_measurement_mismatch = False
        self.min_value = self.max_value = self.mean = self.last = self.median = None
        self.min_entity_id = self.max_entity_id = self.last_entity_id = None
        self.count_sensors = len(self._entity_ids)
        self.states = {}

        self._attr_name = config_entry.data[CONF_NAME]
        self._attr_unique_id = config_entry.unique_id
        self._attr_should_poll = False
        self._attr_icon = ICON

    async def async_added_to_hass(self):
        """Handle added to Hass."""
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                self._entity_ids,
                lambda evt: self._async_min_max_sensor_state_listener(
                    evt.data.get("entity_id"), evt.data.get("new_state")
                ),
            )
        )

        # populate states if not already populated
        if not self.states:
            for entity_id in self._entity_ids:
                state = self.hass.states.get(entity_id)
                # We only want to write the state after populating all states
                self._async_min_max_sensor_state_listener(
                    entity_id, state, write_state=False
                )
            self.async_write_ha_state()
        else:
            self._calc_values()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._config_entry.title

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self._unit_of_measurement_mismatch:
            return None
        return getattr(
            self, next(k for k, v in SENSOR_TYPES.items() if self._sensor_type == v)
        )

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        if self._unit_of_measurement_mismatch:
            return "ERR"
        return self._unit_of_measurement

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            attr: getattr(self, attr)
            for attr in ATTR_TO_PROPERTY
            if getattr(self, attr) is not None
        }

    @callback
    def _async_min_max_sensor_state_listener(self, entity, new_state, write_state=True):
        """Handle the sensor state changes."""
        if (
            new_state is None
            or new_state.state is None
            or new_state.state
            in [
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
            ]
        ):
            self.states[entity] = STATE_UNKNOWN
            self._calc_values()
            if write_state:
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
        if write_state:
            self.async_write_ha_state()

    @callback
    def _calc_values(self):
        """Calculate the values."""
        sensor_values = [
            (entity_id, self.states[entity_id])
            for entity_id in self._entity_ids
            if entity_id in self.states
        ]
        self.min_entity_id, self.min_value = calc_min(sensor_values)
        self.max_entity_id, self.max_value = calc_max(sensor_values)
        self.mean = calc_mean(sensor_values, self._round_digits)
        self.median = calc_median(sensor_values, self._round_digits)
