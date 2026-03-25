"""Helpers for automation."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, Final, Self

import voluptuous as vol

from homeassistant.const import CONF_OPTIONS
from homeassistant.core import HomeAssistant, split_entity_id

from .entity import get_device_class_or_undefined
from .typing import UNDEFINED, ConfigType, UndefinedType

CONF_UNIT: Final = "unit"


class AnyDeviceClassType(Enum):
    """Singleton type for matching any device class."""

    _singleton = 0


ANY_DEVICE_CLASS = AnyDeviceClassType._singleton  # noqa: SLF001


@dataclass(frozen=True, slots=True)
class DomainSpec:
    """Describes how to match and extract a value from an entity.

    Used by triggers and conditions.
    """

    device_class: str | None | AnyDeviceClassType = ANY_DEVICE_CLASS
    value_source: str | None = None
    """Attribute name to extract the value from, or None for state.state."""


@dataclass(frozen=True, slots=True)
class NumericalDomainSpec(DomainSpec):
    """DomainSpec with an optional value converter for numerical triggers."""

    value_converter: Callable[[float], float] | None = None
    """Optional converter for numerical values (e.g. uint8 → percentage)."""


def filter_by_domain_specs(
    hass: HomeAssistant,
    domain_specs: Mapping[str, DomainSpec],
    entities: set[str],
) -> set[str]:
    """Filter entities matching any of the domain specs."""
    result: set[str] = set()
    for entity_id in entities:
        if not (domain_spec := domain_specs.get(split_entity_id(entity_id)[0])):
            continue
        if (
            domain_spec.device_class is not ANY_DEVICE_CLASS
            and get_device_class_or_undefined(hass, entity_id)
            != domain_spec.device_class
        ):
            continue
        result.add(entity_id)
    return result


def get_absolute_description_key(domain: str, key: str) -> str:
    """Return the absolute description key."""
    if not key.startswith("_"):
        return f"{domain}.{key}"
    key = key[1:]  # Remove leading underscore
    if not key:
        return domain
    return key


def get_relative_description_key(domain: str, key: str) -> str:
    """Return the relative description key."""
    platform, *subtype = key.split(".", 1)
    if platform != domain:
        return f"_{key}"
    if not subtype:
        return "_"
    return subtype[0]


def move_top_level_schema_fields_to_options(
    config: ConfigType, options_schema_dict: dict[vol.Marker, Any]
) -> ConfigType:
    """Move top-level fields to options.

    This function is used to help migrating old-style configs to new-style configs
    for triggers and conditions.
    If options is already present, the config is returned as-is.
    """
    if CONF_OPTIONS in config:
        return config

    config = config.copy()
    options = config.setdefault(CONF_OPTIONS, {})

    # Move top-level fields to options
    for key_marked in options_schema_dict:
        key = key_marked.schema
        if key in config:
            options[key] = config.pop(key)

    return config


def move_options_fields_to_top_level(
    config: ConfigType, base_schema: vol.Schema
) -> ConfigType:
    """Move options fields to top-level.

    This function is used to provide backwards compatibility for new-style configs
    for triggers and conditions.

    The config is returned as-is, if any of the following is true:
    - options is not present
    - options is not a dict
    - the config with options field removed fails the base_schema validation (most
    likely due to additional keys being present)

    Those conditions are checked to make it so that only configs that have the structure
    of the new-style are modified, whereas valid old-style configs are preserved.
    """
    options = config.get(CONF_OPTIONS)

    if not isinstance(options, dict):
        return config

    new_config: ConfigType = config.copy()
    new_config.pop(CONF_OPTIONS)

    try:
        new_config = base_schema(new_config)
    except vol.Invalid:
        return config

    new_config.update(options)

    return new_config


@dataclass(frozen=True, kw_only=True)
class ThresholdConfig:
    """Configuration for threshold conditions and triggers."""

    numerical: bool
    entity: str | None
    number: float | None
    unit: str | None | UndefinedType

    @classmethod
    def from_config(cls, config: dict[str, Any] | None) -> Self | None:
        """Create ThresholdConfig from config dict."""
        if config is None:
            return None

        entity: str | None = None
        number: float | None = None
        unit: str | None | UndefinedType = UNDEFINED
        numerical = "number" in config
        if numerical:
            number = config["number"]
            unit = config.get("unit_of_measurement", UNDEFINED)
        else:
            entity = config["entity"]

        return cls(numerical=numerical, number=number, entity=entity, unit=unit)
