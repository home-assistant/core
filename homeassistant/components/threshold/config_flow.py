"""Config flow for Threshold integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_ENTITY_ID, CONF_NAME
from homeassistant.helpers import selector
from homeassistant.helpers.helper_config_entry_flow import (
    HelperConfigFlowHandler,
    HelperFlowStep,
)

from .const import (
    CONF_HYSTERESIS,
    CONF_LOWER,
    CONF_MODE,
    CONF_UPPER,
    DEFAULT_HYSTERESIS,
    DOMAIN,
    THRESHOLD_MODES,
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MODE): selector.selector(
            {"select": {"options": THRESHOLD_MODES}}
        ),
        vol.Required(CONF_HYSTERESIS, default=DEFAULT_HYSTERESIS): selector.selector(
            {"number": {"mode": "box"}}
        ),
        vol.Required(CONF_LOWER, default=0.0): selector.selector(
            {"number": {"mode": "box"}}
        ),
        vol.Required(CONF_UPPER, default=0.0): selector.selector(
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

CONFIG_FLOW = {"user": HelperFlowStep(CONFIG_SCHEMA)}

OPTIONS_FLOW = {"init": HelperFlowStep(OPTIONS_SCHEMA)}


class ConfigFlowHandler(HelperConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Threshold."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return options[CONF_NAME]
