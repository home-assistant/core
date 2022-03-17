"""Config flow for Integration - Riemann sum integral integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.const import (
    CONF_METHOD,
    CONF_NAME,
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
    CONF_CUSTOM_UNIT_ENABLE,
    CONF_CUSTOM_UNIT_OF_MEASUREMENT,
    CONF_ROUND_DIGITS,
    CONF_SOURCE_SENSOR,
    CONF_UNIT_PREFIX,
    CONF_UNIT_TIME,
    DOMAIN,
    INTEGRATION_METHODS,
    METHOD_TRAPEZOIDAL,
)

UNIT_PREFIXES = ["none", "k", "M", "G", "T"]
TIME_UNITS = [TIME_SECONDS, TIME_MINUTES, TIME_HOURS, TIME_DAYS]

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_METHOD, default=METHOD_TRAPEZOIDAL): selector.selector(
            {"select": {"options": INTEGRATION_METHODS}}
        ),
        vol.Required(CONF_ROUND_DIGITS, default=2): selector.selector(
            {"number": {"min": 0, "max": 6, "mode": "box"}}
        ),
        vol.Required(CONF_UNIT_PREFIX, default=TIME_HOURS): selector.selector(
            {"select": {"options": UNIT_PREFIXES}}
        ),
        vol.Required(CONF_UNIT_TIME): selector.selector(
            {"select": {"options": TIME_UNITS}}
        ),
        vol.Required(CONF_CUSTOM_UNIT_ENABLE, default=False): selector.selector(
            {"boolean": {}}
        ),
        vol.Required(CONF_CUSTOM_UNIT_OF_MEASUREMENT): selector.selector({"text": {}}),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.selector({"text": {}}),
        vol.Required(CONF_SOURCE_SENSOR): selector.selector(
            {"entity": {"domain": "sensor"}},
        ),
    }
).extend(OPTIONS_SCHEMA.schema)

CONFIG_FLOW = {"user": HelperFlowStep(CONFIG_SCHEMA)}

OPTIONS_FLOW = {"init": HelperFlowStep(OPTIONS_SCHEMA)}


class ConfigFlowHandler(HelperConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Integration."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"])
