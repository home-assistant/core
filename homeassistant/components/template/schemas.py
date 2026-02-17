"""Shared schemas for config entry and YAML config items."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_ENTITY_PICTURE_TEMPLATE,
    CONF_ICON,
    CONF_ICON_TEMPLATE,
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_UNIQUE_ID,
    CONF_VARIABLES,
)
from homeassistant.helpers import config_validation as cv, selector

from .const import (
    CONF_ATTRIBUTE_TEMPLATES,
    CONF_ATTRIBUTES,
    CONF_AVAILABILITY,
    CONF_AVAILABILITY_TEMPLATE,
    CONF_DEFAULT_ENTITY_ID,
    CONF_PICTURE,
)

TEMPLATE_ENTITY_AVAILABILITY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_AVAILABILITY): cv.template,
    }
)

TEMPLATE_ENTITY_ATTRIBUTES_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ATTRIBUTES): vol.Schema({cv.string: cv.template}),
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

TEMPLATE_ENTITY_ATTRIBUTES_SCHEMA_LEGACY = vol.Schema(
    {
        vol.Optional(CONF_ATTRIBUTE_TEMPLATES, default={}): vol.Schema(
            {cv.string: cv.template}
        ),
    }
)

TEMPLATE_ENTITY_AVAILABILITY_SCHEMA_LEGACY = vol.Schema(
    {
        vol.Optional(CONF_AVAILABILITY_TEMPLATE): cv.template,
    }
)

TEMPLATE_ENTITY_COMMON_SCHEMA_LEGACY = vol.Schema(
    {
        vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
        vol.Optional(CONF_ICON_TEMPLATE): cv.template,
    }
).extend(TEMPLATE_ENTITY_AVAILABILITY_SCHEMA_LEGACY.schema)


def make_template_entity_base_schema(domain: str, default_name: str) -> vol.Schema:
    """Return a schema with default name."""
    return vol.Schema(
        {
            vol.Optional(CONF_DEFAULT_ENTITY_ID): vol.All(
                cv.entity_id, cv.entity_domain(domain)
            ),
            vol.Optional(CONF_ICON): cv.template,
            vol.Optional(CONF_NAME, default=default_name): cv.template,
            vol.Optional(CONF_PICTURE): cv.template,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    )


def make_template_entity_common_modern_schema(
    domain: str,
    default_name: str,
) -> vol.Schema:
    """Return a schema with default name."""
    return vol.Schema(
        {
            vol.Optional(CONF_AVAILABILITY): cv.template,
            vol.Optional(CONF_VARIABLES): cv.SCRIPT_VARIABLES_SCHEMA,
        }
    ).extend(make_template_entity_base_schema(domain, default_name).schema)


def make_template_entity_common_modern_attributes_schema(
    domain: str,
    default_name: str,
) -> vol.Schema:
    """Return a schema with default name."""
    return make_template_entity_common_modern_schema(domain, default_name).extend(
        TEMPLATE_ENTITY_ATTRIBUTES_SCHEMA.schema
    )
