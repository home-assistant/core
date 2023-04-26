"""Support for monitoring if a sensor value is below/above a threshold."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_NAME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_HYSTERESIS, CONF_LOWER, CONF_UPPER

_LOGGER = logging.getLogger(__name__)

ATTR_HYSTERESIS = "hysteresis"
ATTR_LOWER = "lower"
ATTR_POSITION = "position"
ATTR_SENSOR_VALUE = "sensor_value"
ATTR_TYPE = "type"
ATTR_UPPER = "upper"

DEFAULT_NAME = "Threshold"
DEFAULT_HYSTERESIS = 0.0

POSITION_ABOVE = "above"
POSITION_BELOW = "below"
POSITION_IN_RANGE = "in_range"
POSITION_UNKNOWN = "unknown"

TYPE_LOWER = "lower"
TYPE_RANGE = "range"
TYPE_UPPER = "upper"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_HYSTERESIS, default=DEFAULT_HYSTERESIS): vol.Coerce(float),
        vol.Optional(CONF_LOWER): vol.Coerce(float),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UPPER): vol.Coerce(float),
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize threshold config entry."""
    registry = er.async_get(hass)
    device_class = None
    entity_id = er.async_validate_entity_id(
        registry, config_entry.options[CONF_ENTITY_ID]
    )
    hysteresis = config_entry.options[CONF_HYSTERESIS]
    lower = config_entry.options[CONF_LOWER]
    name = config_entry.title
    unique_id = config_entry.entry_id
    upper = config_entry.options[CONF_UPPER]

    async_add_entities(
        [
            ThresholdSensor(
                hass, entity_id, name, lower, upper, hysteresis, device_class, unique_id
            )
        ]
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Threshold sensor."""
    entity_id: str = config[CONF_ENTITY_ID]
    name: str = config[CONF_NAME]
    lower: float | None = config.get(CONF_LOWER)
    upper: float | None = config.get(CONF_UPPER)
    hysteresis: float = config[CONF_HYSTERESIS]
    device_class: BinarySensorDeviceClass | None = config.get(CONF_DEVICE_CLASS)

    if lower is None and upper is None:
        raise ValueError("Lower or Upper thresholds not provided")

    async_add_entities(
        [
            ThresholdSensor(
                hass, entity_id, name, lower, upper, hysteresis, device_class, None
            )
        ],
    )


def _threshold_type(lower: float | None, upper: float | None) -> str:
    """Return the type of threshold this sensor represents."""
    if lower is not None and upper is not None:
        return TYPE_RANGE
    if lower is not None:
        return TYPE_LOWER
    return TYPE_UPPER


class ThresholdSensor(BinarySensorEntity):
    """Representation of a Threshold sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entity_id: str,
        name: str,
        lower: float | None,
        upper: float | None,
        hysteresis: float,
        device_class: BinarySensorDeviceClass | None,
        unique_id: str | None,
    ) -> None:
        """Initialize the Threshold sensor."""
        self._attr_unique_id = unique_id
        self._entity_id = entity_id
        self._name = name
        if lower is not None:
            self._threshold_lower = lower
        if upper is not None:
            self._threshold_upper = upper
        self.threshold_type = _threshold_type(lower, upper)
        self._hysteresis: float = hysteresis
        self._device_class = device_class
        self._state_position = POSITION_UNKNOWN
        self._state: bool | None = None
        self.sensor_value: float | None = None

        def _update_sensor_state() -> None:
            """Handle sensor state changes."""
            if (new_state := hass.states.get(self._entity_id)) is None:
                return

            try:
                self.sensor_value = (
                    None
                    if new_state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]
                    else float(new_state.state)
                )
            except (ValueError, TypeError):
                self.sensor_value = None
                _LOGGER.warning("State is not numerical")

            self._update_state()

        @callback
        def async_threshold_sensor_state_listener(event: Event) -> None:
            """Handle sensor state changes."""
            _update_sensor_state()
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                hass, [entity_id], async_threshold_sensor_state_listener
            )
        )
        _update_sensor_state()

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self) -> bool | None:
        """Return true if sensor is on."""
        return self._state

    @property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return the sensor class of the sensor."""
        return self._device_class

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the sensor."""
        return {
            ATTR_ENTITY_ID: self._entity_id,
            ATTR_HYSTERESIS: self._hysteresis,
            ATTR_LOWER: getattr(self, "_threshold_lower", None),
            ATTR_POSITION: self._state_position,
            ATTR_SENSOR_VALUE: self.sensor_value,
            ATTR_TYPE: self.threshold_type,
            ATTR_UPPER: getattr(self, "_threshold_upper", None),
        }

    @callback
    def _update_state(self) -> None:
        """Update the state."""

        def below(sensor_value: float, threshold: float) -> bool:
            """Determine if the sensor value is below a threshold."""
            return sensor_value < (threshold - self._hysteresis)

        def above(sensor_value: float, threshold: float) -> bool:
            """Determine if the sensor value is above a threshold."""
            return sensor_value > (threshold + self._hysteresis)

        if self.sensor_value is None:
            self._state_position = POSITION_UNKNOWN
            self._state = None
            return

        if self.threshold_type == TYPE_LOWER:
            if self._state is None:
                self._state = False
                self._state_position = POSITION_ABOVE

            if below(self.sensor_value, self._threshold_lower):
                self._state_position = POSITION_BELOW
                self._state = True
            elif above(self.sensor_value, self._threshold_lower):
                self._state_position = POSITION_ABOVE
                self._state = False
            return

        if self.threshold_type == TYPE_UPPER:
            assert self._threshold_upper is not None

            if self._state is None:
                self._state = False
                self._state_position = POSITION_BELOW

            if above(self.sensor_value, self._threshold_upper):
                self._state_position = POSITION_ABOVE
                self._state = True
            elif below(self.sensor_value, self._threshold_upper):
                self._state_position = POSITION_BELOW
                self._state = False
            return

        if self.threshold_type == TYPE_RANGE:
            if self._state is None:
                self._state = True
                self._state_position = POSITION_IN_RANGE

            if below(self.sensor_value, self._threshold_lower):
                self._state_position = POSITION_BELOW
                self._state = False
            if above(self.sensor_value, self._threshold_upper):
                self._state_position = POSITION_ABOVE
                self._state = False
            elif above(self.sensor_value, self._threshold_lower) and below(
                self.sensor_value, self._threshold_upper
            ):
                self._state_position = POSITION_IN_RANGE
                self._state = True
            return
