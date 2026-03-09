"""Provides conditions for batteries."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, NumberDeviceClass
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.const import (
    CONF_ABOVE,
    CONF_BELOW,
    CONF_OPTIONS,
    CONF_TARGET,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, State, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.condition import (
    ATTR_BEHAVIOR,
    BEHAVIOR_ALL,
    BEHAVIOR_ANY,
    Condition,
    ConditionConfig,
    EntityConditionBase,
    make_entity_state_condition,
)
from homeassistant.helpers.entity import get_device_class
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

DEVICE_CLASSES_BATTERY_PERCENTAGE: dict[str, str] = {
    SENSOR_DOMAIN: SensorDeviceClass.BATTERY,
    NUMBER_DOMAIN: NumberDeviceClass.BATTERY,
}


def _filter_by_device_class(
    device_class: str,
) -> Callable[[HomeAssistant, set[str]], set[str]]:
    """Create a filter function that filters entities by device class."""

    def _filter(hass: HomeAssistant, entities: set[str]) -> set[str]:
        return {
            entity_id
            for entity_id in entities
            if _get_device_class_or_undefined(hass, entity_id) == device_class
        }

    return _filter


def _get_device_class_or_undefined(
    hass: HomeAssistant, entity_id: str
) -> str | None | UndefinedType:
    """Get the device class of an entity or UNDEFINED if not found."""
    try:
        return get_device_class(hass, entity_id)
    except HomeAssistantError:
        return UNDEFINED


PERCENTAGE_OPTIONS_SCHEMA: dict[vol.Marker, Any] = {
    vol.Required(ATTR_BEHAVIOR, default=BEHAVIOR_ANY): vol.In(
        [BEHAVIOR_ANY, BEHAVIOR_ALL]
    ),
    vol.Optional(CONF_ABOVE): vol.Coerce(float),
    vol.Optional(CONF_BELOW): vol.Coerce(float),
}

PERCENTAGE_CONDITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
        vol.Required(CONF_OPTIONS): vol.All(
            PERCENTAGE_OPTIONS_SCHEMA,
            cv.has_at_least_one_key(CONF_ABOVE, CONF_BELOW),
        ),
    }
)


class BatteryPercentageCondition(EntityConditionBase):
    """Condition for battery percentage level."""

    _domain = SENSOR_DOMAIN
    _schema = PERCENTAGE_CONDITION_SCHEMA

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize the battery percentage condition."""
        super().__init__(hass, config)
        assert config.options is not None
        self._above: float | None = config.options.get(CONF_ABOVE)
        self._below: float | None = config.options.get(CONF_BELOW)

    def entity_filter(self, entities: set[str]) -> set[str]:
        """Filter entities by battery device class across sensor and number domains."""
        return {
            entity_id
            for entity_id in entities
            if (domain := split_entity_id(entity_id)[0])
            in DEVICE_CLASSES_BATTERY_PERCENTAGE
            and _get_device_class_or_undefined(self._hass, entity_id)
            == DEVICE_CLASSES_BATTERY_PERCENTAGE[domain]
        }

    def is_valid_state(self, entity_state: State) -> bool:
        """Check if the battery percentage is within the specified range."""
        try:
            value = float(entity_state.state)
        except ValueError, TypeError:
            return False

        if self._above is not None and value <= self._above:
            return False
        if self._below is not None and value >= self._below:
            return False
        return True


CONDITIONS: dict[str, type[Condition]] = {
    "is_low": make_entity_state_condition(
        BINARY_SENSOR_DOMAIN,
        STATE_ON,
        entity_filter=_filter_by_device_class(BinarySensorDeviceClass.BATTERY),
    ),
    "is_high": make_entity_state_condition(
        BINARY_SENSOR_DOMAIN,
        STATE_OFF,
        entity_filter=_filter_by_device_class(BinarySensorDeviceClass.BATTERY),
    ),
    "is_charging": make_entity_state_condition(
        BINARY_SENSOR_DOMAIN,
        STATE_ON,
        entity_filter=_filter_by_device_class(BinarySensorDeviceClass.BATTERY_CHARGING),
    ),
    "is_not_charging": make_entity_state_condition(
        BINARY_SENSOR_DOMAIN,
        STATE_OFF,
        entity_filter=_filter_by_device_class(BinarySensorDeviceClass.BATTERY_CHARGING),
    ),
    "percentage": BatteryPercentageCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for batteries."""
    return CONDITIONS
