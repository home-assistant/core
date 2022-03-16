"""Config flow for Times of the Day integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.const import (
    CONF_AFTER,
    CONF_BEFORE,
    CONF_NAME,
    SUN_EVENT_SUNRISE,
    SUN_EVENT_SUNSET,
)
from homeassistant.helpers import selector
from homeassistant.helpers.helper_config_entry_flow import (
    HelperConfigFlowHandler,
    HelperFlowFormStep,
    HelperFlowMenuStep,
)

from .const import (
    CONF_ABSOLUTE_TIME,
    CONF_AFTER_OFFSET,
    CONF_AFTER_TIME,
    CONF_BEFORE_OFFSET,
    CONF_BEFORE_TIME,
    DOMAIN,
)

_BEFORE_AFTER_OPTIONS = [SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET, CONF_ABSOLUTE_TIME]

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_AFTER): selector.selector(
            {"select": {"options": _BEFORE_AFTER_OPTIONS}}
        ),
        vol.Optional(CONF_AFTER_TIME): selector.selector({"time": {}}),
        vol.Required(CONF_AFTER_OFFSET, default={"seconds": 0}): selector.selector(
            {"duration": {}}
        ),
        vol.Required(CONF_BEFORE): selector.selector(
            {"select": {"options": _BEFORE_AFTER_OPTIONS}}
        ),
        vol.Optional(CONF_BEFORE_TIME): selector.selector({"time": {}}),
        vol.Required(CONF_BEFORE_OFFSET, default={"seconds": 0}): selector.selector(
            {"duration": {}}
        ),
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
