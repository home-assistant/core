"""Config flow for the Generic Thermostat integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.climate import HVACMode
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import PRECISION_HALVES, PRECISION_TENTHS, PRECISION_WHOLE
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)

from .const import (
    CONF_AC_MODE,
    CONF_COLD_TOLERANCE,
    CONF_HEATER,
    CONF_HOT_TOLERANCE,
    CONF_INITIAL_HVAC_MODE,
    CONF_KEEP_ALIVE,
    CONF_MAX_TEMP,
    CONF_MIN_DUR,
    CONF_MIN_TEMP,
    CONF_NAME,
    CONF_PRECISION,
    CONF_SENSOR,
    CONF_TARGET_TEMP,
    CONF_TEMP_STEP,
    DEFAULT_MIN_TEMP,
    DEFAULT_NAME,
    DEFAULT_TOLERANCE,
    DOMAIN,
)

CONF_PRECISION_LIST = [
    selector.SelectOptionDict(value=str(PRECISION_TENTHS), label=str(PRECISION_TENTHS)),
    selector.SelectOptionDict(value=str(PRECISION_HALVES), label=str(PRECISION_HALVES)),
    selector.SelectOptionDict(value=str(PRECISION_WHOLE), label=str(PRECISION_WHOLE)),
]

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_AC_MODE): bool,
        vol.Optional(CONF_MAX_TEMP): float,
        vol.Optional(CONF_MIN_TEMP, default=DEFAULT_MIN_TEMP): float,
        vol.Optional(CONF_MIN_DUR): selector.DurationSelector(
            selector.DurationSelectorConfig()
        ),
        vol.Optional(CONF_COLD_TOLERANCE, default=DEFAULT_TOLERANCE): float,
        vol.Optional(CONF_HOT_TOLERANCE, default=DEFAULT_TOLERANCE): float,
        vol.Optional(CONF_TARGET_TEMP): float,
        vol.Optional(CONF_KEEP_ALIVE): selector.DurationSelector(
            selector.DurationSelectorConfig()
        ),
        vol.Optional(CONF_INITIAL_HVAC_MODE): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[HVACMode.COOL, HVACMode.HEAT, HVACMode.OFF],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Optional(CONF_PRECISION): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=CONF_PRECISION_LIST,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Optional(CONF_TEMP_STEP): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=CONF_PRECISION_LIST,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
    }
)


OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA),
}


class GenericThermostatConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Generic Thermostat."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SchemaOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the form."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                        vol.Required(CONF_HEATER): selector.EntitySelector(
                            selector.EntitySelectorConfig(domain=["input_boolean"]),
                        ),
                        vol.Required(CONF_SENSOR): selector.EntitySelector(
                            selector.EntitySelectorConfig(
                                domain=["sensor"],
                                device_class=SensorDeviceClass.TEMPERATURE,
                            ),
                        ),
                    }
                ),
            )
        return self.async_create_entry(title=DEFAULT_NAME, data=user_input)
