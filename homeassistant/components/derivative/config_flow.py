"""Config flow for Derivative integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.const import (
    CONF_SOURCE,
    TIME_DAYS,
    TIME_HOURS,
    TIME_MINUTES,
    TIME_SECONDS,
)
from homeassistant.helpers import selector
from homeassistant.helpers.helper_config_entry_flow import (
    HelperConfigFlowHandler,
    HelperFlowStep,
)

from .const import (
    CONF_ROUND_DIGITS,
    CONF_TIME_WINDOW,
    CONF_UNIT_PREFIX,
    CONF_UNIT_TIME,
    DOMAIN,
)

UNIT_PREFIXES = ["none", "n", "µ", "m", "k", "M", "G", "T"]
TIME_UNITS = [TIME_SECONDS, TIME_MINUTES, TIME_HOURS, TIME_DAYS]

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ROUND_DIGITS, default=2): selector.selector(
            {"number": {"min": 0, "max": 6, "mode": "box"}}
        ),
        vol.Required(CONF_TIME_WINDOW): selector.selector(
            {"duration": {"as_dict": True}}
        ),
        vol.Required(CONF_UNIT_PREFIX, default=TIME_HOURS): selector.selector(
            {"select": {"options": UNIT_PREFIXES}}
        ),
        vol.Required(CONF_UNIT_TIME): selector.selector(
            {"select": {"options": TIME_UNITS}}
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required("name"): selector.selector({"text": {}}),
        vol.Required(CONF_SOURCE): selector.selector(
            {"entity": {"domain": "sensor"}},
        ),
    }
).extend(OPTIONS_SCHEMA.schema)

CONFIG_FLOW = {"user": HelperFlowStep(CONFIG_SCHEMA)}

OPTIONS_FLOW = {"init": HelperFlowStep(OPTIONS_SCHEMA)}


class ConfigFlowHandler(HelperConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Derivative."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"])
