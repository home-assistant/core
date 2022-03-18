"""Config flow for Times of the Day integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector
from homeassistant.helpers.helper_config_entry_flow import (
    HelperConfigFlowHandler,
    HelperFlowFormStep,
    HelperFlowMenuStep,
)

from .const import CONF_AFTER_TIME, CONF_BEFORE_TIME, DOMAIN

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_AFTER_TIME): selector.selector({"time": {}}),
        vol.Optional(CONF_BEFORE_TIME): selector.selector({"time": {}}),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.selector({"text": {}}),
    }
).extend(OPTIONS_SCHEMA.schema)

CONFIG_FLOW: dict[str, HelperFlowFormStep | HelperFlowMenuStep] = {
    "user": HelperFlowFormStep(CONFIG_SCHEMA)
}

OPTIONS_FLOW: dict[str, HelperFlowFormStep | HelperFlowMenuStep] = {
    "init": HelperFlowFormStep(OPTIONS_SCHEMA)
}


class ConfigFlowHandler(HelperConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Times of the Day."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"])
