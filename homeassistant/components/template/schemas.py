"""Shared schemas for config entry and YAML config items."""

import probatio

from homeassistant.const import (
    CONF_CONDITIONS,
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
from .validators import BlockedTemplateAttributes, validate_attributes

TEMPLATE_ENTITY_AVAILABILITY_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_AVAILABILITY): cv.template,
    }
)

TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_NAME): cv.template,
        probatio.Optional(CONF_DEVICE_ID): selector.DeviceSelector(),
    }
).extend(TEMPLATE_ENTITY_AVAILABILITY_SCHEMA.schema)


TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA = {
    probatio.Optional(CONF_OPTIMISTIC): cv.boolean,
}


def make_template_entity_common_schema(
    domain: str,
    default_name: str,
    blocked_attributes: BlockedTemplateAttributes | None = None,
) -> probatio.Schema:
    """Return a schema with default name."""
    return probatio.Schema(
        {
            probatio.Optional(CONF_AVAILABILITY): cv.template,
            probatio.Optional(CONF_DEFAULT_ENTITY_ID): probatio.All(
                cv.entity_id, cv.entity_domain(domain)
            ),
            probatio.Optional(CONF_ICON): cv.template,
            probatio.Optional(CONF_NAME, default=default_name): cv.template,
            probatio.Optional(CONF_PICTURE): cv.template,
            probatio.Optional(CONF_UNIQUE_ID): cv.string,
            probatio.Optional(CONF_VARIABLES): cv.SCRIPT_VARIABLES_SCHEMA,
            probatio.Optional(CONF_CONDITIONS): cv.CONDITIONS_SCHEMA,
            probatio.Optional(CONF_ATTRIBUTES): probatio.Schema(
                probatio.Any(
                    probatio.All(
                        {cv.string: cv.template},
                        validate_attributes(default_name, blocked_attributes),
                    ),
                    cv.template,
                )
            ),
        }
    )
