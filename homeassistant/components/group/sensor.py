"""This platform allows several sensors to be grouped into one sensor to provide numeric combinations."""
from __future__ import annotations

from datetime import timedelta
import logging
import statistics
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DEVICE_CLASSES_SCHEMA,
    DOMAIN,
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    STATE_CLASSES_SCHEMA,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE_CLASS,
    CONF_ENTITIES,
    CONF_NAME,
    CONF_TYPE,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.dt import UTC, now

from . import GroupEntity

DEFAULT_NAME = "Sensor Group"
CONF_ALL = "all"
CONF_ROUND_DIGITS = "round_digits"

ATTR_MIN_VALUE = "min_value"
ATTR_MIN_ENTITY_ID = "min_entity_id"
ATTR_MAX_VALUE = "max_value"
ATTR_MAX_ENTITY_ID = "max_entity_id"
ATTR_MEAN = "mean"
ATTR_MEDIAN = "median"
ATTR_LAST = "last"
ATTR_LAST_ENTITY_ID = "last_entity_id"
ATTR_RANGE = "range"
ATTR_SUM = "sum"
SENSOR_TYPES = {
    ATTR_MIN_VALUE: "min",
    ATTR_MAX_VALUE: "max",
    ATTR_MEAN: "mean",
    ATTR_MEDIAN: "median",
    ATTR_LAST: "last",
    ATTR_RANGE: "range",
    ATTR_SUM: "sum",
}
SENSOR_TYPE_TO_ATTR = {v: k for k, v in SENSOR_TYPES.items()}

# No limit on parallel updates to enable a group calling another group
PARALLEL_UPDATES = 0

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITIES): cv.entities_domain(DOMAIN),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_ALL, default=False): cv.boolean,
        vol.Optional(CONF_TYPE, default=SENSOR_TYPES[ATTR_MAX_VALUE]): vol.All(
            cv.string, vol.In(SENSOR_TYPES.values())
        ),
        vol.Optional(CONF_ROUND_DIGITS, default=2): vol.Coerce(int),
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): str,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(
            CONF_STATE_CLASS, default=SensorStateClass.MEASUREMENT
        ): STATE_CLASSES_SCHEMA,
    }
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Switch Group platform."""
    async_add_entities(
        [
            SensorGroup(
                config.get(CONF_UNIQUE_ID),
                config[CONF_NAME],
                config[CONF_ENTITIES],
                config[CONF_ALL],
                config[CONF_TYPE],
                config[CONF_ROUND_DIGITS],
                config.get(CONF_UNIT_OF_MEASUREMENT),
                config.get(CONF_DEVICE_CLASS),
                config[CONF_STATE_CLASS],
            )
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Switch Group config entry."""
    registry = er.async_get(hass)
    entities = er.async_validate_entity_ids(
        registry, config_entry.options[CONF_ENTITIES]
    )
    async_add_entities(
        [
            SensorGroup(
                config_entry.entry_id,
                config_entry.title,
                entities,
                config_entry.options[CONF_ALL],
                config_entry.options[CONF_TYPE],
                int(config_entry.options[CONF_ROUND_DIGITS]),
                config_entry.options.get(CONF_UNIT_OF_MEASUREMENT),
                config_entry.options.get(CONF_DEVICE_CLASS),
                config_entry.options[CONF_STATE_CLASS],
            )
        ]
    )


def calc_min(sensor_values: list[tuple[str, Any]]) -> tuple[str | None, float | None]:
    """Calculate min value."""
    val: float | None = None
    entity_id: str | None = None
    for sensor_id, sensor_value in sensor_values:
        if sensor_value not in [STATE_UNKNOWN, STATE_UNAVAILABLE] and (
            val is None or val > sensor_value
        ):
            entity_id, val = sensor_id, sensor_value
    return entity_id, val


def calc_max(sensor_values: list[tuple[str, Any]]) -> tuple[str | None, float | None]:
    """Calculate max value."""
    val: float | None = None
    entity_id: str | None = None
    for sensor_id, sensor_value in sensor_values:
        if sensor_value not in [STATE_UNKNOWN, STATE_UNAVAILABLE] and (
            val is None or val < sensor_value
        ):
            entity_id, val = sensor_id, sensor_value
    return entity_id, val


def calc_mean(sensor_values: list[tuple[str, Any]], round_digits: int) -> float | None:
    """Calculate mean value."""
    result = [
        sensor_value
        for _, sensor_value in sensor_values
        if sensor_value not in [STATE_UNKNOWN, STATE_UNAVAILABLE]
    ]

    if not result:
        return None
    value: float = round(statistics.mean(result), round_digits)
    return value


def calc_median(
    sensor_values: list[tuple[str, Any]], round_digits: int
) -> float | None:
    """Calculate median value."""
    result = [
        sensor_value
        for _, sensor_value in sensor_values
        if sensor_value not in [STATE_UNKNOWN, STATE_UNAVAILABLE]
    ]

    if not result:
        return None
    value: float = round(statistics.median(result), round_digits)
    return value


def calc_range(sensor_values: list[tuple[str, Any]], round_digits: int) -> float | None:
    """Calculate range value."""
    result = [
        sensor_value
        for _, sensor_value in sensor_values
        if sensor_value not in [STATE_UNKNOWN, STATE_UNAVAILABLE]
    ]

    if not result:
        return None
    value: float = round(max(result) - min(result), round_digits)
    return value


def calc_sum(sensor_values: list[tuple[str, Any]], round_digits: int) -> float:
    """Calculate a sum of values."""
    result = 0
    for _, sensor_value in sensor_values:
        try:
            result += sensor_value
        except TypeError:
            continue

    value: float = round(result, round_digits)
    return value


class SensorGroup(GroupEntity, SensorEntity):
    """Representation of a sensor group."""

    _attr_available = False
    _attr_should_poll = False
    _attr_icon = "mdi:calculator"

    def __init__(
        self,
        unique_id: str | None,
        name: str,
        entity_ids: list[str],
        mode: bool,
        sensor_type: str,
        round_digits: int,
        unit_of_measurement: str | None,
        state_class: str | None,
        device_class: str | None,
    ) -> None:
        """Initialize a sensor group."""
        self._entity_ids = entity_ids
        self._sensor_type = sensor_type
        self._round_digits = round_digits
        self._attr_state_class = state_class
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._attr_name = name
        if name == DEFAULT_NAME:
            self._attr_name = f"{DEFAULT_NAME} {sensor_type}".capitalize()
        self._attr_extra_state_attributes = {ATTR_ENTITY_ID: entity_ids}
        self._attr_unique_id = unique_id
        self.mode = all if mode else any
        self._sensor_attr = SENSOR_TYPE_TO_ATTR[self._sensor_type]
        self.min_value: float | None = None
        self.max_value: float | None = None
        self.mean: float | None = None
        self.last: float | None = None
        self.median: float | None = None
        self.range: float | None = None
        self.sum: float | None = None
        self.min_entity_id: str | None = None
        self.max_entity_id: str | None = None
        self.last_entity_id: str | None = None

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        @callback
        def async_state_changed_listener(event: Event) -> None:
            """Handle child updates."""
            self.async_set_context(event.context)
            self.async_defer_or_update_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._entity_ids, async_state_changed_listener
            )
        )

        await super().async_added_to_hass()

    @callback
    def async_update_group_state(self) -> None:
        """Query all members and determine the sensor group state."""
        states = []
        last_updated = now(UTC) - timedelta(days=1)
        sensor_values: list[tuple[str, Any]] = []
        for entity_id in self._entity_ids:
            if (state := self.hass.states.get(entity_id)) is not None:
                states.append(state.state)
                if state.last_updated > last_updated:
                    self.last = float(state.state)
                    self.last_entity_id = entity_id
                try:
                    sensor_values.append((entity_id, float(state.state)))
                except ValueError:
                    _LOGGER.warning(
                        "Unable to use state. Only numerical states are supported, entity %s excluded from calculation",
                        entity_id,
                    )
                    continue

        valid_state = self.mode(
            state not in (STATE_UNKNOWN, STATE_UNAVAILABLE) for state in states
        )

        if not valid_state:
            # Set as unknown if any / all member is unknown or unavailable
            self._attr_native_value = None
        else:
            # Calculate values
            self._calc_values(sensor_values)
            self._attr_native_value = getattr(self, self._sensor_attr)

        # Set group as unavailable if all members are unavailable or missing
        self._attr_available = any(state != STATE_UNAVAILABLE for state in states)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the sensor."""
        attributes: dict[str, Any] = {ATTR_ENTITY_ID: self._entity_ids}
        if self._sensor_type == "min":
            attributes[ATTR_MIN_ENTITY_ID] = self.min_entity_id
        if self._sensor_type == "max":
            attributes[ATTR_MAX_ENTITY_ID] = self.max_entity_id
        if self._sensor_type == "last":
            attributes[ATTR_LAST_ENTITY_ID] = self.last_entity_id
        return attributes

    @callback
    def _calc_values(self, sensor_values: list[tuple[str, Any]]) -> None:
        """Calculate the values."""

        self.min_entity_id, self.min_value = calc_min(sensor_values)
        self.max_entity_id, self.max_value = calc_max(sensor_values)
        self.mean = calc_mean(sensor_values, self._round_digits)
        self.median = calc_median(sensor_values, self._round_digits)
        self.range = calc_range(sensor_values, self._round_digits)
        self.sum = calc_sum(sensor_values, self._round_digits)
