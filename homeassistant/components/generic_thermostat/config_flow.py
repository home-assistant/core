"""Config flow for Generic hygrostat."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.components import fan, switch
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.const import (
    CONF_NAME,
    DEGREE,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
)
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)

from .const import (
    CONF_AC_MODE,
    CONF_COLD_TOLERANCE,
    CONF_HEATER,
    CONF_HOT_TOLERANCE,
    CONF_MAX_TEMP,
    CONF_MIN_DUR,
    CONF_MIN_TEMP,
    CONF_PRECISION,
    CONF_PRESETS,
    CONF_SENSOR,
    CONF_TEMP_STEP,
    DEFAULT_TOLERANCE,
    DOMAIN,
)

PRECISIONS = [PRECISION_TENTHS, PRECISION_HALVES, PRECISION_WHOLE]

OPTIONS_SCHEMA = {
    vol.Required(CONF_AC_MODE): selector.BooleanSelector(
        selector.BooleanSelectorConfig(),
    ),
    vol.Required(CONF_SENSOR): selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain=SENSOR_DOMAIN, device_class=SensorDeviceClass.TEMPERATURE
        )
    ),
    vol.Required(CONF_HEATER): selector.EntitySelector(
        selector.EntitySelectorConfig(domain=[fan.DOMAIN, switch.DOMAIN])
    ),
    vol.Required(
        CONF_COLD_TOLERANCE, default=DEFAULT_TOLERANCE
    ): selector.NumberSelector(
        selector.NumberSelectorConfig(
            mode=selector.NumberSelectorMode.BOX, unit_of_measurement=DEGREE, step=0.1
        )
    ),
    vol.Required(
        CONF_HOT_TOLERANCE, default=DEFAULT_TOLERANCE
    ): selector.NumberSelector(
        selector.NumberSelectorConfig(
            mode=selector.NumberSelectorMode.BOX, unit_of_measurement=DEGREE, step=0.1
        )
    ),
    vol.Optional(CONF_MIN_DUR): selector.DurationSelector(
        selector.DurationSelectorConfig(allow_negative=False)
    ),
    vol.Optional(CONF_MIN_TEMP): selector.NumberSelector(
        selector.NumberSelectorConfig(
            mode=selector.NumberSelectorMode.BOX, unit_of_measurement=DEGREE, step=0.1
        )
    ),
    vol.Optional(CONF_MAX_TEMP): selector.NumberSelector(
        selector.NumberSelectorConfig(
            mode=selector.NumberSelectorMode.BOX, unit_of_measurement=DEGREE, step=0.1
        )
    ),
    vol.Optional(CONF_PRECISION): vol.All(
        selector.SelectSelector(
            selector.SelectSelectorConfig(
                mode=selector.SelectSelectorMode.DROPDOWN,
                options=[
                    selector.SelectOptionDict(
                        value=str(precision),
                        label=f"{precision}{DEGREE}",
                    )
                    for precision in PRECISIONS
                ],
            )
        ),
        vol.Coerce(float),
    ),
    vol.Optional(CONF_TEMP_STEP): vol.All(
        selector.SelectSelector(
            selector.SelectSelectorConfig(
                mode=selector.SelectSelectorMode.DROPDOWN,
                options=[
                    selector.SelectOptionDict(
                        value=str(precision),
                        label=f"{precision}{DEGREE}",
                    )
                    for precision in PRECISIONS
                ],
            )
        ),
        vol.Coerce(float),
    ),
}

PRESETS_SCHEMA = {
    vol.Optional(v): selector.NumberSelector(
        selector.NumberSelectorConfig(
            mode=selector.NumberSelectorMode.BOX, unit_of_measurement=DEGREE, step=0.1
        )
    )
    for v in CONF_PRESETS.values()
}

CONFIG_SCHEMA = {
    vol.Required(CONF_NAME): selector.TextSelector(),
    **OPTIONS_SCHEMA,
}


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(vol.Schema(CONFIG_SCHEMA), next_step="presets"),
    "presets": SchemaFlowFormStep(vol.Schema(PRESETS_SCHEMA)),
}


async def get_options_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Get options schema."""
    if CONF_PRECISION in handler.options:
        for p in PRECISIONS:
            if handler.options[CONF_PRECISION] == p:
                handler.options[CONF_PRECISION] = str(p)
    if CONF_TEMP_STEP in handler.options:
        for p in PRECISIONS:
            if handler.options[CONF_TEMP_STEP] == p:
                handler.options[CONF_TEMP_STEP] = str(p)
    return vol.Schema(OPTIONS_SCHEMA)


OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(get_options_schema, next_step="presets"),
    "presets": SchemaFlowFormStep(vol.Schema(PRESETS_SCHEMA)),
}


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"])
