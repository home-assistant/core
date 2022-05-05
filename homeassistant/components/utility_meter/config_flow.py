"""Config flow for Utility Meter integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
)

from .const import (
    BIMONTHLY,
    CONF_METER_DELTA_VALUES,
    CONF_METER_NET_CONSUMPTION,
    CONF_METER_OFFSET,
    CONF_METER_TYPE,
    CONF_SOURCE_SENSOR,
    CONF_TARIFFS,
    DAILY,
    DOMAIN,
    HOURLY,
    MONTHLY,
    QUARTER_HOURLY,
    QUARTERLY,
    WEEKLY,
    YEARLY,
)

METER_TYPES = [
    selector.SelectOptionDict(value="none", label="No cycle"),
    selector.SelectOptionDict(value=QUARTER_HOURLY, label="Every 15 minutes"),
    selector.SelectOptionDict(value=HOURLY, label="Hourly"),
    selector.SelectOptionDict(value=DAILY, label="Daily"),
    selector.SelectOptionDict(value=WEEKLY, label="Weekly"),
    selector.SelectOptionDict(value=MONTHLY, label="Monthly"),
    selector.SelectOptionDict(value=BIMONTHLY, label="Every two months"),
    selector.SelectOptionDict(value=QUARTERLY, label="Quarterly"),
    selector.SelectOptionDict(value=YEARLY, label="Yearly"),
]


def _validate_config(data: Any) -> Any:
    """Validate config."""
    try:
        vol.Unique()(data[CONF_TARIFFS])
    except vol.Invalid as exc:
        raise SchemaFlowError("tariffs_not_unique") from exc

    return data


OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SOURCE_SENSOR): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor"),
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.TextSelector(),
        vol.Required(CONF_SOURCE_SENSOR): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor"),
        ),
        vol.Required(CONF_METER_TYPE): selector.SelectSelector(
            selector.SelectSelectorConfig(options=METER_TYPES),
        ),
        vol.Required(CONF_METER_OFFSET, default=0): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=28,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="days",
            ),
        ),
        vol.Required(CONF_TARIFFS, default=[]): selector.SelectSelector(
            selector.SelectSelectorConfig(options=[], custom_value=True, multiple=True),
        ),
        vol.Required(
            CONF_METER_NET_CONSUMPTION, default=False
        ): selector.BooleanSelector(),
        vol.Required(
            CONF_METER_DELTA_VALUES, default=False
        ): selector.BooleanSelector(),
    }
)

CONFIG_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
    "user": SchemaFlowFormStep(CONFIG_SCHEMA, validate_user_input=_validate_config)
}

OPTIONS_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA)
}


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Utility Meter."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""

        return cast(str, options[CONF_NAME])
