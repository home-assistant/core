"""Config flow for Threshold integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_ENTITY_ID, CONF_NAME
from homeassistant.helpers import selector
from homeassistant.helpers.helper_config_entry_flow import (
    HelperConfigFlowHandler,
    HelperFlowError,
    HelperFlowStep,
)

from .const import CONF_HYSTERESIS, CONF_LOWER, CONF_UPPER, DEFAULT_HYSTERESIS, DOMAIN


def _validate_mode(data: Any) -> Any:
    """Validate the threshold mode."""
    if data[CONF_LOWER] is None and data[CONF_UPPER] is None:
        raise HelperFlowError("need_lower_upper")
    return data


OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HYSTERESIS, default=DEFAULT_HYSTERESIS): selector.selector(
            {"number": {"mode": "box"}}
        ),
        vol.Required(CONF_LOWER, default=None): selector.selector(
            {"number": {"mode": "box"}}
        ),
        vol.Required(CONF_UPPER, default=None): selector.selector(
            {"number": {"mode": "box"}}
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.selector({"text": {}}),
        vol.Required(CONF_ENTITY_ID): selector.selector(
            {"entity": {"domain": "sensor"}}
        ),
    }
).extend(OPTIONS_SCHEMA.schema)

CONFIG_FLOW = {
    "user": HelperFlowStep(CONFIG_SCHEMA, validate_user_input=_validate_mode)
}

OPTIONS_FLOW = {
    "init": HelperFlowStep(OPTIONS_SCHEMA, validate_user_input=_validate_mode)
}


class ConfigFlowHandler(HelperConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Threshold."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return options[CONF_NAME]
