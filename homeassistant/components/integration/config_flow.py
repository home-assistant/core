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
    selector.SelectOptionDict(value="none", label="none"),
    selector.SelectOptionDict(value="k", label="k (kilo)"),
    selector.SelectOptionDict(value="M", label="M (mega)"),
    selector.SelectOptionDict(value="G", label="G (giga)"),
    selector.SelectOptionDict(value="T", label="T (tera)"),
]
TIME_UNITS = [
    selector.SelectOptionDict(value=TIME_SECONDS, label="s (seconds)"),
    selector.SelectOptionDict(value=TIME_MINUTES, label="min (minutes)"),
    selector.SelectOptionDict(value=TIME_HOURS, label="h (hours)"),
    selector.SelectOptionDict(value=TIME_DAYS, label="d (days)"),
]
INTEGRATION_METHODS = [
    selector.SelectOptionDict(value=METHOD_TRAPEZOIDAL, label="Trapezoidal rule"),
    selector.SelectOptionDict(value=METHOD_LEFT, label="Left Riemann sum"),
    selector.SelectOptionDict(value=METHOD_RIGHT, label="Right Riemann sum"),
]

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ROUND_DIGITS, default=2): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=6, mode=selector.NumberSelectorMode.BOX
            ),
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.TextSelector(),
        vol.Required(CONF_SOURCE_SENSOR): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Required(CONF_METHOD, default=METHOD_TRAPEZOIDAL): selector.SelectSelector(
            selector.SelectSelectorConfig(options=INTEGRATION_METHODS),
        ),
        vol.Required(CONF_ROUND_DIGITS, default=2): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=6,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="decimals",
            ),
        ),
        vol.Required(CONF_UNIT_PREFIX, default="none"): selector.SelectSelector(
            selector.SelectSelectorConfig(options=UNIT_PREFIXES),
        ),
        vol.Required(CONF_UNIT_TIME, default=TIME_HOURS): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=TIME_UNITS, mode=selector.SelectSelectorMode.DROPDOWN
            ),
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
