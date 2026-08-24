"""Shared schemas for config entry and YAML config items."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from itertools import chain
import logging
from typing import Any

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
from homeassistant.helpers.template import Template

from .const import (
    CONF_ATTRIBUTES,
    CONF_AVAILABILITY,
    CONF_DEFAULT_ENTITY_ID,
    CONF_PICTURE,
)

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


@dataclass
class BlockedTemplateAttributes:
    """Blocked template attributes."""

    attributes: tuple[type[StrEnum], ...] | type[StrEnum] | None = None
    device_class: bool = False


def log_validation_error(
    result: Any,
    template: Template,
    attribute: str,
    entity_id: str,
    exception: vol.Invalid,
):
    """Log template entity validation error."""
    logging.getLogger(f"{__package__}.{entity_id.split('.', maxsplit=1)[0]}").error(
        (
            "Error validating template result '%s' "
            "from template '%s' "
            "for attribute '%s' in entity %s "
            "validation message '%s'"
        ),
        result,
        template,
        attribute,
        entity_id,
        exception.msg,
    )


def validate_attributes(
    breadcrumb: str,
    blocked_attributes: BlockedTemplateAttributes | None,
) -> Callable[[dict], dict]:
    """Validate entity attributes."""

    def validate(obj: dict):
        if blocked_attributes is None:
            return obj

        if (
            blocked_attributes.attributes is None
            and not blocked_attributes.device_class
        ):
            return obj

        _blocked_attributes: set[str]
        if (attributes := blocked_attributes.attributes) is None:
            _blocked_attributes = set()
        elif isinstance(attributes, tuple):
            _blocked_attributes = set(chain(*attributes))
        else:
            _blocked_attributes = set(attributes)

        if blocked_attributes.device_class:
            _blocked_attributes.add("device_class")

        if blocked := (_blocked_attributes.intersection(set(obj.keys()))):
            raise vol.Invalid(
                f"Unsupported attribute(s) found for {breadcrumb}: {', '.join(blocked)}"
            )

        return obj

    return validate


def make_template_entity_common_schema(
    domain: str,
    default_name: str,
    blocked_attributes: BlockedTemplateAttributes | None = None,
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
                vol.Any(
                    vol.All(
                        {cv.string: cv.template},
                        validate_attributes(default_name, blocked_attributes),
                    ),
                    cv.template,
                )
            ),
        }
    )
