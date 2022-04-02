"""Config flow for Threshold integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_ENTITY_ID, CONF_NAME
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
)

from .const import CONF_HYSTERESIS, CONF_LOWER, CONF_UPPER, DEFAULT_HYSTERESIS, DOMAIN


def _validate_mode(data: Any) -> Any:
    """Validate the threshold mode, and set limits to None if not set."""
    if CONF_LOWER not in data and CONF_UPPER not in data:
        raise SchemaFlowError("need_lower_upper")
    return {CONF_LOWER: None, CONF_UPPER: None, **data}


OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HYSTERESIS, default=DEFAULT_HYSTERESIS): selector.selector(
            selector.SelectorType.NUMBER,
            selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX),
        ),
        vol.Optional(CONF_LOWER): selector.selector(
            selector.SelectorType.NUMBER,
            selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX),
        ),
        vol.Optional(CONF_UPPER): selector.selector(
            selector.SelectorType.NUMBER,
            selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX),
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.selector(selector.SelectorType.TEXT),
        vol.Required(CONF_ENTITY_ID): selector.selector(
            selector.SelectorType.ENTITY, selector.EntitySelectorConfig(domain="sensor")
        ),
    }
).extend(OPTIONS_SCHEMA.schema)

CONFIG_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
    "user": SchemaFlowFormStep(CONFIG_SCHEMA, validate_user_input=_validate_mode)
}

OPTIONS_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA, validate_user_input=_validate_mode)
}


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Threshold."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return options[CONF_NAME]
