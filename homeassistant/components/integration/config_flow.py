"""Config flow for Integration - Riemann sum integral integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.const import (
    CONF_METHOD,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    TIME_DAYS,
    TIME_HOURS,
    TIME_MINUTES,
    TIME_SECONDS,
)
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
)

from .const import (
    CONF_ROUND_DIGITS,
    CONF_SOURCE_SENSOR,
    CONF_UNIT_PREFIX,
    CONF_UNIT_TIME,
    DOMAIN,
    METHOD_LEFT,
    METHOD_RIGHT,
    METHOD_TRAPEZOIDAL,
)

UNIT_PREFIXES = [
    {"value": "none", "label": "none"},
    {"value": "k", "label": "k (kilo)"},
    {"value": "M", "label": "M (mega)"},
    {"value": "G", "label": "G (giga)"},
    {"value": "T", "label": "T (tera)"},
]
TIME_UNITS = [
    {"value": TIME_SECONDS, "label": "s (seconds)"},
    {"value": TIME_MINUTES, "label": "min (minutes)"},
    {"value": TIME_HOURS, "label": "h (hours)"},
    {"value": TIME_DAYS, "label": "d (days)"},
]
INTEGRATION_METHODS = [
    {"value": METHOD_TRAPEZOIDAL, "label": "Trapezoidal rule"},
    {"value": METHOD_LEFT, "label": "Left Riemann sum"},
    {"value": METHOD_RIGHT, "label": "Right Riemann sum"},
]

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ROUND_DIGITS, default=2): selector.selector(
            {"number": {"min": 0, "max": 6, "mode": "box"}}
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.selector({"text": {}}),
        vol.Required(CONF_SOURCE_SENSOR): selector.selector(
            {"entity": {"domain": "sensor"}},
        ),
        vol.Required(CONF_METHOD, default=METHOD_TRAPEZOIDAL): selector.selector(
            {"select": {"options": INTEGRATION_METHODS}}
        ),
        vol.Required(CONF_ROUND_DIGITS, default=2): selector.selector(
            {
                "number": {
                    "min": 0,
                    "max": 6,
                    "mode": "box",
                    CONF_UNIT_OF_MEASUREMENT: "decimals",
                }
            }
        ),
        vol.Required(CONF_UNIT_PREFIX, default="none"): selector.selector(
            {"select": {"options": UNIT_PREFIXES}}
        ),
        vol.Required(CONF_UNIT_TIME, default=TIME_HOURS): selector.selector(
            {"select": {"options": TIME_UNITS}}
        ),
    }
)

CONFIG_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
    "user": SchemaFlowFormStep(CONFIG_SCHEMA)
}

OPTIONS_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA)
}


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Integration."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"])
