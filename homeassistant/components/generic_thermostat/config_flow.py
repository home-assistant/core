"""Config flow for Generic hygrostat."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.climate import HVACMode
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    CONF_NAME,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
)
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)

from .climate import (
    CONF_AC_MODE,
    CONF_COLD_TOLERANCE,
    CONF_HEATER,
    CONF_HOT_TOLERANCE,
    CONF_INITIAL_HVAC_MODE,
    CONF_KEEP_ALIVE,
    CONF_MAX_TEMP,
    CONF_MIN_DUR,
    CONF_MIN_TEMP,
    CONF_PRECISION,
    CONF_SENSOR,
    CONF_TARGET_TEMP,
    CONF_TEMP_STEP,
    DEFAULT_TOLERANCE,
    DOMAIN,
)

OPTIONS_SCHEMA = {
    vol.Required(CONF_SENSOR): selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain=SENSOR_DOMAIN, device_class=SensorDeviceClass.TEMPERATURE
        )
    ),
    vol.Required(CONF_HEATER): selector.EntitySelector(
        selector.EntitySelectorConfig(domain=SWITCH_DOMAIN)
    ),
    vol.Required(CONF_AC_MODE): selector.BooleanSelector(
        selector.BooleanSelectorConfig(),
    ),
    vol.Required(
        CONF_COLD_TOLERANCE, default=DEFAULT_TOLERANCE
    ): selector.NumberSelector(),
    vol.Required(
        CONF_HOT_TOLERANCE, default=DEFAULT_TOLERANCE
    ): selector.NumberSelector(),
    vol.Optional(CONF_TARGET_TEMP): selector.NumberSelector(),
    vol.Optional(CONF_MIN_DUR): selector.DurationSelector(
        selector.DurationSelectorConfig(allow_negative=False)
    ),
    vol.Optional(CONF_MIN_TEMP): selector.NumberSelector(),
    vol.Optional(CONF_MAX_TEMP): selector.NumberSelector(),
    vol.Optional(CONF_INITIAL_HVAC_MODE): selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[HVACMode.COOL, HVACMode.HEAT, HVACMode.OFF],
            translation_key=CONF_INITIAL_HVAC_MODE,
        )
    ),
    vol.Optional(CONF_PRECISION): vol.In(
        [PRECISION_TENTHS, PRECISION_HALVES, PRECISION_WHOLE]
    ),
    vol.Optional(CONF_KEEP_ALIVE): selector.DurationSelector(
        selector.DurationSelectorConfig(allow_negative=False, enable_day=False)
    ),
    vol.Optional(CONF_TEMP_STEP): vol.In(
        [PRECISION_TENTHS, PRECISION_HALVES, PRECISION_WHOLE]
    ),
}

CONFIG_SCHEMA = {
    vol.Required(CONF_NAME): selector.TextSelector(),
    **OPTIONS_SCHEMA,
}


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(vol.Schema(OPTIONS_SCHEMA)),
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(vol.Schema(CONFIG_SCHEMA)),
}


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"])
