"""Shared schemas for config entry and YAML config items."""

from collections.abc import Callable
from enum import StrEnum
from itertools import chain
from typing import TypeVar

import voluptuous as vol

from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_ICON,
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_UNIQUE_ID,
    CONF_VARIABLES,
)
from homeassistant.helpers import config_validation as cv, selector

from .const import (
    CONF_ATTRIBUTES,
    CONF_AVAILABILITY,
    CONF_DEFAULT_ENTITY_ID,
    CONF_PICTURE,
)

_AttributeEnum = TypeVar("_AttributeEnum", bound=type[StrEnum])

TEMPLATE_ENTITY_AVAILABILITY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_AVAILABILITY): cv.template,
    }
)

TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.template,
        vol.Optional(CONF_DEVICE_ID): selector.DeviceSelector(),
    }
).extend(TEMPLATE_ENTITY_AVAILABILITY_SCHEMA.schema)


TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA = {
    vol.Optional(CONF_OPTIMISTIC): cv.boolean,
}


def _blocked_attributes(
    default_name: str,
    blocked_attributes: tuple[_AttributeEnum, ...] | _AttributeEnum | None,
    block_device_class: bool,
) -> Callable[[dict], dict]:

    def validate(obj: dict):
        if blocked_attributes is None and not block_device_class:
            return obj

        _blocked_attributes: set[str]
        if blocked_attributes is None:
            _blocked_attributes = set()
        elif isinstance(blocked_attributes, tuple):
            _blocked_attributes = set(chain(*blocked_attributes))
        else:
            _blocked_attributes = set(blocked_attributes)

        if block_device_class:
            _blocked_attributes.add("device_class")

        if blocked := (_blocked_attributes.intersection(set(obj.keys()))):
            raise vol.Invalid(
                f"Unsupported attribute(s) found for {default_name}: {', '.join(blocked)}"
            )

        return obj

    return validate


def make_template_entity_common_schema(
    domain: str,
    default_name: str,
    blocked_attributes: tuple[_AttributeEnum, ...] | _AttributeEnum | None = None,
    block_device_class: bool = False,
) -> vol.Schema:
    """Return a schema with default name."""
    return vol.Schema(
        {
            vol.Optional(CONF_AVAILABILITY): cv.template,
            vol.Optional(CONF_DEFAULT_ENTITY_ID): vol.All(
                cv.entity_id, cv.entity_domain(domain)
            ),
            vol.Optional(CONF_ICON): cv.template,
            vol.Optional(CONF_NAME, default=default_name): cv.template,
            vol.Optional(CONF_PICTURE): cv.template,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
            vol.Optional(CONF_VARIABLES): cv.SCRIPT_VARIABLES_SCHEMA,
            vol.Optional(CONF_ATTRIBUTES): vol.Schema(
                vol.All(
                    {cv.string: cv.template},
                    _blocked_attributes(
                        default_name, blocked_attributes, block_device_class
                    ),
                )
            ),
        }
    )
