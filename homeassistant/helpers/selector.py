"""Selectors for Home Assistant."""
from __future__ import annotations

from collections.abc import Callable
from datetime import time as time_sys
from typing import Any, cast

import voluptuous as vol

from homeassistant.const import CONF_MODE, CONF_UNIT_OF_MEASUREMENT
from homeassistant.core import split_entity_id, valid_entity_id
from homeassistant.util import decorator

from . import config_validation as cv

SELECTORS = decorator.Registry()


def _get_selector_class(config: Any) -> type[Selector]:
    """Get selector class type."""
    if not isinstance(config, dict):
        raise vol.Invalid("Expected a dictionary")

    if len(config) != 1:
        raise vol.Invalid(f"Only one type can be specified. Found {', '.join(config)}")

    selector_type = list(config)[0]

    if (selector_class := SELECTORS.get(selector_type)) is None:
        raise vol.Invalid(f"Unknown selector type {selector_type} found")

    return cast(type[Selector], selector_class)


def selector(config: Any) -> Selector:
    """Instantiate a selector."""
    selector_class = _get_selector_class(config)
    selector_type = list(config)[0]

    # Selectors can be empty
    if config[selector_type] is None:
        return selector_class({selector_type: {}})

    return selector_class(config)


def validate_selector(config: Any) -> dict:
    """Validate a selector."""
    selector_class = _get_selector_class(config)
    selector_type = list(config)[0]

    # Selectors can be empty
    if config[selector_type] is None:
        return {selector_type: {}}

    return {
        selector_type: cast(dict, selector_class.CONFIG_SCHEMA(config[selector_type]))
    }


class Selector:
    """Base class for selectors."""

    CONFIG_SCHEMA: Callable
    config: Any
    selector_type: str

    def __init__(self, config: Any) -> None:
        """Instantiate a selector."""
        self.config = self.CONFIG_SCHEMA(config[self.selector_type])

    def serialize(self) -> Any:
        """Serialize Selector for voluptuous_serialize."""
        return {"selector": {self.selector_type: self.config}}


SINGLE_ENTITY_SELECTOR_CONFIG_SCHEMA = vol.Schema(
    {
        # Integration that provided the entity
        vol.Optional("integration"): str,
        # Domain the entity belongs to
        vol.Optional("domain"): str,
        # Device class of the entity
        vol.Optional("device_class"): str,
    }
)


@SELECTORS.register("entity")
class EntitySelector(Selector):
    """Selector of a single or list of entities."""

    selector_type = "entity"

    CONFIG_SCHEMA = SINGLE_ENTITY_SELECTOR_CONFIG_SCHEMA.extend(
        {vol.Optional("multiple", default=False): cv.boolean}
    )

    def __call__(self, data: Any) -> str | list[str]:
        """Validate the passed selection."""

        def validate(e_or_u: str) -> str:
            e_or_u = cv.entity_id_or_uuid(e_or_u)
            if not valid_entity_id(e_or_u):
                return e_or_u
            if allowed_domain := self.config.get("domain"):
                domain = split_entity_id(e_or_u)[0]
                if domain != allowed_domain:
                    raise vol.Invalid(
                        f"Entity {e_or_u} belongs to domain {domain}, "
                        f"expected {allowed_domain}"
                    )
            return e_or_u

        if not self.config["multiple"]:
            return validate(data)
        if not isinstance(data, list):
            raise vol.Invalid("Value should be a list")
        return cast(list, vol.Schema([validate])(data))  # Output is a list


@SELECTORS.register("device")
class DeviceSelector(Selector):
    """Selector of a single or list of devices."""

    selector_type = "device"

    CONFIG_SCHEMA = vol.Schema(
        {
            # Integration linked to it with a config entry
            vol.Optional("integration"): str,
            # Manufacturer of device
            vol.Optional("manufacturer"): str,
            # Model of device
            vol.Optional("model"): str,
            # Device has to contain entities matching this selector
            vol.Optional("entity"): SINGLE_ENTITY_SELECTOR_CONFIG_SCHEMA,
            vol.Optional("multiple", default=False): cv.boolean,
        }
    )

    def __call__(self, data: Any) -> str | list[str]:
        """Validate the passed selection."""
        if not self.config["multiple"]:
            return cv.string(data)
        if not isinstance(data, list):
            raise vol.Invalid("Value should be a list")
        return [cv.string(val) for val in data]


@SELECTORS.register("area")
class AreaSelector(Selector):
    """Selector of a single or list of areas."""

    selector_type = "area"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional("entity"): SINGLE_ENTITY_SELECTOR_CONFIG_SCHEMA,
            vol.Optional("device"): DeviceSelector.CONFIG_SCHEMA,
            vol.Optional("multiple", default=False): cv.boolean,
        }
    )

    def __call__(self, data: Any) -> str | list[str]:
        """Validate the passed selection."""
        if not self.config["multiple"]:
            return cv.string(data)
        if not isinstance(data, list):
            raise vol.Invalid("Value should be a list")
        return [cv.string(val) for val in data]


@SELECTORS.register("number")
class NumberSelector(Selector):
    """Selector of a numeric value."""

    selector_type = "number"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required("min"): vol.Coerce(float),
            vol.Required("max"): vol.Coerce(float),
            vol.Optional("step", default=1): vol.All(
                vol.Coerce(float), vol.Range(min=1e-3)
            ),
            vol.Optional(CONF_UNIT_OF_MEASUREMENT): str,
            vol.Optional(CONF_MODE, default="slider"): vol.In(["box", "slider"]),
        }
    )

    def __call__(self, data: Any) -> float:
        """Validate the passed selection."""
        value: float = vol.Coerce(float)(data)

        if not self.config["min"] <= value <= self.config["max"]:
            raise vol.Invalid(f"Value {value} is too small or too large")

        return value


@SELECTORS.register("addon")
class AddonSelector(Selector):
    """Selector of a add-on."""

    selector_type = "addon"

    CONFIG_SCHEMA = vol.Schema({})

    def __call__(self, data: Any) -> str:
        """Validate the passed selection."""
        return cv.string(data)


@SELECTORS.register("boolean")
class BooleanSelector(Selector):
    """Selector of a boolean value."""

    selector_type = "boolean"

    CONFIG_SCHEMA = vol.Schema({})

    def __call__(self, data: Any) -> bool:
        """Validate the passed selection."""
        value: bool = vol.Coerce(bool)(data)
        return value


@SELECTORS.register("time")
class TimeSelector(Selector):
    """Selector of a time value."""

    selector_type = "time"

    CONFIG_SCHEMA = vol.Schema({})

    def __call__(self, data: Any) -> time_sys:
        """Validate the passed selection."""
        return cv.time(data)


@SELECTORS.register("target")
class TargetSelector(Selector):
    """Selector of a target value (area ID, device ID, entity ID etc).

    Value should follow cv.TARGET_SERVICE_FIELDS format.
    """

    selector_type = "target"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional("entity"): EntitySelector.CONFIG_SCHEMA,
            vol.Optional("device"): DeviceSelector.CONFIG_SCHEMA,
        }
    )

    TARGET_SELECTION_SCHEMA = vol.Schema(cv.TARGET_SERVICE_FIELDS)

    def __call__(self, data: Any) -> dict[str, list[str]]:
        """Validate the passed selection."""
        target: dict[str, list[str]] = self.TARGET_SELECTION_SCHEMA(data)
        return target


@SELECTORS.register("action")
class ActionSelector(Selector):
    """Selector of an action sequence (script syntax)."""

    selector_type = "action"

    CONFIG_SCHEMA = vol.Schema({})

    def __call__(self, data: Any) -> Any:
        """Validate the passed selection."""
        return data


@SELECTORS.register("object")
class ObjectSelector(Selector):
    """Selector for an arbitrary object."""

    selector_type = "object"

    CONFIG_SCHEMA = vol.Schema({})

    def __call__(self, data: Any) -> Any:
        """Validate the passed selection."""
        return data


@SELECTORS.register("text")
class StringSelector(Selector):
    """Selector for a multi-line text string."""

    selector_type = "text"

    CONFIG_SCHEMA = vol.Schema({vol.Optional("multiline", default=False): bool})

    def __call__(self, data: Any) -> str:
        """Validate the passed selection."""
        text = cv.string(data)
        return text


@SELECTORS.register("select")
class SelectSelector(Selector):
    """Selector for an single-choice input select."""

    selector_type = "select"

    CONFIG_SCHEMA = vol.Schema(
        {vol.Required("options"): vol.All([str], vol.Length(min=1))}
    )

    def __call__(self, data: Any) -> Any:
        """Validate the passed selection."""
        selected_option = vol.In(self.config["options"])(cv.string(data))
        return selected_option
