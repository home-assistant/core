"""Selectors for Home Assistant."""
from __future__ import annotations

from collections.abc import Callable
from datetime import time as time_sys
from typing import Any, cast

import voluptuous as vol

from homeassistant.const import CONF_MODE, CONF_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.util import decorator

from . import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from .entity import get_device_class
from .typing import ConfigType

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
    config: ConfigType
    hass: HomeAssistant

    def __init__(self, hass: HomeAssistant, config: ConfigType) -> None:
        """Instantiate a selector."""
        self.config = self.CONFIG_SCHEMA(config)
        self.hass = hass


@SELECTORS.register("entity")
class EntitySelector(Selector):
    """Selector of a single entity."""

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
        entity_registry = er.async_get(self.hass)
        entity_id = er.async_resolve_entity_id(
            entity_registry, cv.entity_id_or_uuid(data)
        )
        if not entity_id:
            raise vol.Invalid(f"Unknown entity {data}")
        entry = entity_registry.async_get(entity_id)
        if not entry:
            raise vol.Invalid(f"Entity {entity_id} not registered")
        domain = split_entity_id(entity_id)[0]

        if "device_class" in self.config:
            device_class = get_device_class(self.hass, entity_id)
            expected_device_class = self.config["device_class"]
            if device_class != expected_device_class:
                raise vol.Invalid(
                    f"Entity {entity_id} has device class {device_class}, "
                    f"expected {expected_device_class}"
                )

        if "domain" in self.config and domain != self.config["domain"]:
            raise vol.Invalid(
                f"Entity {entity_id} belongs to domain {domain}, "
                f"expected {self.config['domain']}"
            )

        if "integration" in self.config and entry.domain != self.config["integration"]:
            raise vol.Invalid(
                f"Entity {entity_id} belongs to integration {entry.domain}, "
                f"expected {self.config['integration']}"
            )

        return entity_id


@SELECTORS.register("device")
class DeviceSelector(Selector):
    """Selector of a single device."""

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
        device_id = cv.string(data)
        device_registry = dr.async_get(self.hass)
        entity_registry = er.async_get(self.hass)
        entry = device_registry.async_get(device_id)
        if not entry:
            raise vol.Invalid(f"Device {device_id} not registered")

        if "entity" in self.config:
            entity_validator = EntitySelector(self.hass, self.config["entity"])
            device_entities = er.async_entries_for_device(
                entity_registry, device_id, include_disabled_entities=True
            )
            has_match = False
            for entity_entry in device_entities:
                try:
                    entity_validator({"entity_id": entity_entry.entity_id})
                except vol.Error:
                    pass
                else:
                    has_match = True
                    break
            if not has_match:
                raise vol.Invalid(f"Device {device_id} has no matching entity")

        if "integration" in self.config:
            has_match = False
            for config_entry_id in entry.config_entries:
                config_entry = self.hass.config_entries.async_get_entry(config_entry_id)
                assert config_entry
                if config_entry.domain == self.config["integration"]:
                    has_match = True
                break
            if not has_match:
                raise vol.Invalid(f"Device {device_id} has no matching config entry")

        if (
            "manufacturer" in self.config
            and entry.manufacturer != self.config["manufacturer"]
        ):
            raise vol.Invalid(
                f"Device {device_id} has manufacturer {entry.manufacturer}, "
                f"expected {self.config['manufacturer']}"
            )

        if "model" in self.config and entry.manufacturer != self.config["model"]:
            raise vol.Invalid(
                f"Device {device_id} has model {entry.model}, "
                f"expected {self.config['model']}"
            )

        return device_id


@SELECTORS.register("area")
class AreaSelector(Selector):
    """Selector of a single area."""

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional("entity"): EntitySelector.CONFIG_SCHEMA,
            vol.Optional("entity"): DeviceSelector.CONFIG_SCHEMA,
        }
    )

    def __call__(self, data: Any) -> str:
        """Validate the passed selection."""
        area_id = cv.string(data)
        area_registry = ar.async_get(self.hass)
        device_registry = dr.async_get(self.hass)
        entity_registry = er.async_get(self.hass)
        entry = area_registry.async_get_area(area_id)
        if not entry:
            raise vol.Invalid(f"Area {area_id} not registered")

        if "device" in self.config:
            device_validator = DeviceSelector(self.hass, self.config["device"])
            area_devices = dr.async_entries_for_area(device_registry, area_id)
            has_match = False
            for device_entry in area_devices:
                try:
                    device_validator({"device_id": device_entry.id})
                except vol.Error:
                    pass
                else:
                    has_match = True
                    break
            if not has_match:
                raise vol.Invalid(f"Area {area_id} has no matching device")

        if "entity" in self.config:
            entity_validator = EntitySelector(self.hass, self.config["entity"])
            area_entities = er.async_entries_for_area(entity_registry, area_id)
            has_match = False
            for entity_entry in area_entities:
                try:
                    entity_validator({"entity_id": entity_entry.entity_id})
                except vol.Error:
                    pass
                else:
                    has_match = True
                    break
            if not has_match:
                raise vol.Invalid(f"Area {area_id} has no matching entity")

        return area_id


@SELECTORS.register("number")
class NumberSelector(Selector):
    """Selector of a numeric value."""

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

    CONFIG_SCHEMA = vol.Schema({})

    def __call__(self, data: Any) -> bool:
        """Validate the passed selection."""
        value: bool = vol.Coerce(bool)(data)
        return value


@SELECTORS.register("boolean")
class BooleanSelector(Selector):
    """Selector of a boolean value."""

    CONFIG_SCHEMA = vol.Schema({})

    def __call__(self, data: Any) -> str:
        """Validate the passed selection."""
        return cv.string(data)


@SELECTORS.register("time")
class TimeSelector(Selector):
    """Selector of a time value."""

    CONFIG_SCHEMA = vol.Schema({})

    def __call__(self, data: Any) -> time_sys:
        """Validate the passed selection."""
        return cv.time(data)


@SELECTORS.register("target")
class TargetSelector(Selector):
    """Selector of a target value (area ID, device ID, entity ID etc).

    Value should follow cv.ENTITY_SERVICE_FIELDS format.
    """

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


@SELECTORS.register("action")
class ActionSelector(Selector):
    """Selector of an action sequence (script syntax)."""

    CONFIG_SCHEMA = vol.Schema({})


@SELECTORS.register("object")
class ObjectSelector(Selector):
    """Selector for an arbitrary object."""

    CONFIG_SCHEMA = vol.Schema({})


@SELECTORS.register("text")
class StringSelector(Selector):
    """Selector for a multi-line text string."""

    CONFIG_SCHEMA = vol.Schema({vol.Optional("multiline", default=False): bool})


@SELECTORS.register("select")
class SelectSelector(Selector):
    """Selector for an single-choice input select."""

    CONFIG_SCHEMA = vol.Schema(
        {vol.Required("options"): vol.All([str], vol.Length(min=1))}
    )
