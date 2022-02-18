"""Selectors for Home Assistant."""
from __future__ import annotations

from collections.abc import Callable
import contextlib
from datetime import time as time_sys
from typing import Any, cast

import voluptuous as vol

from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    CONF_MODE,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import split_entity_id
from homeassistant.util import decorator

from . import config_validation as cv

SELECTORS = decorator.Registry()


def validate_selector(config: Any) -> dict:
    """Validate a selector."""
    if not isinstance(config, dict):
        raise vol.Invalid("Expected a dictionary")

    if len(config) != 1:
        raise vol.Invalid(f"Only one type can be specified. Found {', '.join(config)}")

    selector_type = list(config)[0]

    if (selector_class := SELECTORS.get(selector_type)) is None:
        raise vol.Invalid(f"Unknown selector type {selector_type} found")

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
    name: str

    def __init__(self, config: Any) -> None:
        """Instantiate a selector."""
        self.config = self.CONFIG_SCHEMA(config)

    def serialize(self) -> Any:
        """Serialize Selector for voluptuous_serialize."""
        return {"selector": {self.name: self.config}}


@SELECTORS.register("entity")
class EntitySelector(Selector):
    """Selector of a single entity."""

    name = "entity"

    CONFIG_SCHEMA = vol.Schema(
        {
            # Integration that provided the entity
            vol.Optional("integration"): str,
            # Domain the entity belongs to
            vol.Optional("domain"): str,
            # Device class of the entity
            vol.Optional("device_class"): str,
        }
    )

    def __call__(self, data: Any) -> str:
        """Validate the passed selection."""
        with contextlib.suppress(vol.Invalid):
            entity_id = cv.entity_id(data)
            domain = split_entity_id(entity_id)[0]

            if "domain" in self.config and domain != self.config["domain"]:
                raise vol.Invalid(
                    f"Entity {entity_id} belongs to domain {domain}, "
                    f"expected {self.config['domain']}"
                )

            return entity_id
        return cv.entity_id_or_uuid(data)


@SELECTORS.register("device")
class DeviceSelector(Selector):
    """Selector of a single device."""

    name = "device"

    CONFIG_SCHEMA = vol.Schema(
        {
            # Integration linked to it with a config entry
            vol.Optional("integration"): str,
            # Manufacturer of device
            vol.Optional("manufacturer"): str,
            # Model of device
            vol.Optional("model"): str,
            # Device has to contain entities matching this selector
            vol.Optional("entity"): EntitySelector.CONFIG_SCHEMA,
        }
    )

    def __call__(self, data: Any) -> str:
        """Validate the passed selection."""
        return cv.string(data)


@SELECTORS.register("area")
class AreaSelector(Selector):
    """Selector of a single area."""

    name = "area"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional("entity"): EntitySelector.CONFIG_SCHEMA,
            vol.Optional("entity"): DeviceSelector.CONFIG_SCHEMA,
        }
    )

    def __call__(self, data: Any) -> str:
        """Validate the passed selection."""
        return cv.string(data)


@SELECTORS.register("number")
class NumberSelector(Selector):
    """Selector of a numeric value."""

    name = "number"

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

    name = "addon"

    CONFIG_SCHEMA = vol.Schema({})

    def __call__(self, data: Any) -> bool:
        """Validate the passed selection."""
        value: bool = vol.Coerce(bool)(data)
        return value


@SELECTORS.register("boolean")
class BooleanSelector(Selector):
    """Selector of a boolean value."""

    name = "boolean"

    CONFIG_SCHEMA = vol.Schema({})

    def __call__(self, data: Any) -> str:
        """Validate the passed selection."""
        return cv.string(data)


@SELECTORS.register("time")
class TimeSelector(Selector):
    """Selector of a time value."""

    name = "time"

    CONFIG_SCHEMA = vol.Schema({})

    def __call__(self, data: Any) -> time_sys:
        """Validate the passed selection."""
        return cv.time(data)


@SELECTORS.register("target")
class TargetSelector(Selector):
    """Selector of a target value (area ID, device ID, entity ID etc).

    Value should follow cv.ENTITY_SERVICE_FIELDS format.
    """

    name = "target"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional("entity"): vol.Schema(
                {
                    vol.Optional("domain"): str,
                    vol.Optional("device_class"): str,
                    vol.Optional("integration"): str,
                }
            ),
            vol.Optional("device"): vol.Schema(
                {
                    vol.Optional("integration"): str,
                    vol.Optional("manufacturer"): str,
                    vol.Optional("model"): str,
                }
            ),
        }
    )

    TARGET_SELECTION_SCHEMA = vol.Schema(
        {
            vol.Optional(ATTR_AREA_ID): vol.All(cv.ensure_list, str),
            vol.Optional(ATTR_DEVICE_ID): vol.All(cv.ensure_list, str),
            vol.Optional(ATTR_ENTITY_ID): vol.All(
                cv.ensure_list, cv.entity_ids_or_uuids
            ),
        }
    )

    def __call__(self, data: Any) -> dict[str, list[str]]:
        """Validate the passed selection."""
        target: dict[str, list[str]] = self.TARGET_SELECTION_SCHEMA(data)
        return target


@SELECTORS.register("action")
class ActionSelector(Selector):
    """Selector of an action sequence (script syntax)."""

    name = "action"

    CONFIG_SCHEMA = vol.Schema({})

    def __call__(self, data: Any) -> Any:
        """Validate the passed selection."""
        return data


@SELECTORS.register("object")
class ObjectSelector(Selector):
    """Selector for an arbitrary object."""

    name = "object"

    CONFIG_SCHEMA = vol.Schema({})

    def __call__(self, data: Any) -> Any:
        """Validate the passed selection."""
        return data


@SELECTORS.register("text")
class StringSelector(Selector):
    """Selector for a multi-line text string."""

    name = "text"

    CONFIG_SCHEMA = vol.Schema({vol.Optional("multiline", default=False): bool})

    def __call__(self, data: Any) -> str:
        """Validate the passed selection."""
        text = cv.string(data)
        return text


@SELECTORS.register("select")
class SelectSelector(Selector):
    """Selector for an single-choice input select."""

    name = "select"

    CONFIG_SCHEMA = vol.Schema(
        {vol.Required("options"): vol.All([str], vol.Length(min=1))}
    )

    def __call__(self, data: Any) -> Any:
        """Validate the passed selection."""
        selected_option = vol.In(self.config["options"])(cv.string(data))
        return selected_option
