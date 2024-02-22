"""Config flow for Integration - Riemann sum integral integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.counter import DOMAIN as COUNTER_DOMAIN
from homeassistant.components.input_number import DOMAIN as INPUT_NUMBER_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_METHOD, CONF_NAME, UnitOfTime
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
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
    selector.SelectOptionDict(value="k", label="k (kilo)"),
    selector.SelectOptionDict(value="M", label="M (mega)"),
    selector.SelectOptionDict(value="G", label="G (giga)"),
    selector.SelectOptionDict(value="T", label="T (tera)"),
]
TIME_UNITS = [
    UnitOfTime.SECONDS,
    UnitOfTime.MINUTES,
    UnitOfTime.HOURS,
    UnitOfTime.DAYS,
]
INTEGRATION_METHODS = [
    METHOD_TRAPEZOIDAL,
    METHOD_LEFT,
    METHOD_RIGHT,
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
            selector.EntitySelectorConfig(
                domain=[COUNTER_DOMAIN, INPUT_NUMBER_DOMAIN, SENSOR_DOMAIN]
            ),
        ),
        vol.Required(CONF_METHOD, default=METHOD_TRAPEZOIDAL): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=INTEGRATION_METHODS, translation_key=CONF_METHOD
            ),
        ),
        vol.Required(CONF_ROUND_DIGITS, default=2): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=6,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="decimals",
            ),
        ),
        vol.Optional(CONF_UNIT_PREFIX): selector.SelectSelector(
            selector.SelectSelectorConfig(options=UNIT_PREFIXES),
        ),
        vol.Required(CONF_UNIT_TIME, default=UnitOfTime.HOURS): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=TIME_UNITS,
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key=CONF_UNIT_TIME,
            ),
        ),
    }
)

CONFIG_FLOW = {
    "user": SchemaFlowFormStep(CONFIG_SCHEMA),
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA),
}


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Integration."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"])
