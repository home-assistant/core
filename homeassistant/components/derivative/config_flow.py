"""Config flow for Derivative integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_NAME, CONF_SOURCE, UnitOfTime
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)

from .const import (
    CONF_ROUND_DIGITS,
    CONF_TIME_WINDOW,
    CONF_UNIT_PREFIX,
    CONF_UNIT_TIME,
    DOMAIN,
)

UNIT_PREFIXES = [
    selector.SelectOptionDict(value="none", label="none"),
    selector.SelectOptionDict(value="nano", label="n (nano)"),
    selector.SelectOptionDict(value="micro", label="µ (micro)"),
    selector.SelectOptionDict(value="milli", label="m (milli)"),
    selector.SelectOptionDict(value="kilo", label="k (kilo)"),
    selector.SelectOptionDict(value="mega", label="M (mega)"),
    selector.SelectOptionDict(value="giga", label="G (giga)"),
    selector.SelectOptionDict(value="tera", label="T (tera)"),
    selector.SelectOptionDict(value="peta", label="P (peta)"),
]
TIME_UNITS = [
    selector.SelectOptionDict(value=UnitOfTime.SECONDS, label="Seconds"),
    selector.SelectOptionDict(value=UnitOfTime.MINUTES, label="Minutes"),
    selector.SelectOptionDict(value=UnitOfTime.HOURS, label="Hours"),
    selector.SelectOptionDict(value=UnitOfTime.DAYS, label="Days"),
]

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ROUND_DIGITS, default=2): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=6,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="decimals",
            ),
        ),
        vol.Required(CONF_TIME_WINDOW): selector.DurationSelector(),
        vol.Required(CONF_UNIT_PREFIX, default="none"): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=UNIT_PREFIXES, translation_key="unit_prefix"
            ),
        ),
        vol.Required(CONF_UNIT_TIME, default=UnitOfTime.HOURS): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=TIME_UNITS, translation_key="time_unit"
            ),
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.TextSelector(),
        vol.Required(CONF_SOURCE): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=SENSOR_DOMAIN),
        ),
    }
).extend(OPTIONS_SCHEMA.schema)

CONFIG_FLOW = {
    "user": SchemaFlowFormStep(CONFIG_SCHEMA),
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA),
}


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Derivative."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options[CONF_NAME])
