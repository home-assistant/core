"""Config flow for Curve integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.components.input_boolean import DOMAIN as INPUT_BOOLEAN_DOMAIN
from homeassistant.components.input_number import DOMAIN as INPUT_NUMBER_DOMAIN
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)

from .const import CONF_SEGMENTS, CONF_SOURCE, DOMAIN
from .helpers import parse_segments


async def validate_user_input(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate user input."""
    user_input[CONF_SEGMENTS] = [
        seg.to_dict() for seg in parse_segments(user_input[CONF_SEGMENTS])
    ]
    return user_input


async def _get_options_dict(_handler: SchemaCommonFlowHandler | None) -> dict:
    return {
        vol.Optional(CONF_SOURCE): selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=[
                    INPUT_BOOLEAN_DOMAIN,
                    INPUT_NUMBER_DOMAIN,
                    NUMBER_DOMAIN,
                    SENSOR_DOMAIN,
                ],
            ),
        ),
        vol.Required(CONF_SEGMENTS): selector.TextSelector(
            selector.TextSelectorConfig(
                multiline=True,
                type=selector.TextSelectorType.TEXT,
            )
        ),
    }


async def get_config_schema(
    handler: SchemaCommonFlowHandler | None,
) -> vol.Schema:
    """Return schema for configuration."""
    options = await _get_options_dict(handler)
    return vol.Schema(
        {
            vol.Required(CONF_NAME): selector.TextSelector(),
            **options,
        }
    )


async def get_options_schema(
    handler: SchemaCommonFlowHandler | None,
) -> vol.Schema:
    """Return schema for options."""
    options = await _get_options_dict(handler)
    return vol.Schema(options)


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        schema=get_config_schema, validate_user_input=validate_user_input
    )
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        schema=get_options_schema, validate_user_input=validate_user_input
    )
}


class CurveConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config/options flow for Curve."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW
    options_flow_reloads = True

    VERSION = 1
    MINOR_VERSION = 1

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return str(options[CONF_NAME])
