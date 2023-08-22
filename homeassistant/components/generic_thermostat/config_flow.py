"""Config flow for the Generic Thermostat integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.climate import HVACMode
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import PRECISION_HALVES, PRECISION_TENTHS, PRECISION_WHOLE
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

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
    DEFAULT_NAME,
    DEFAULT_TOLERANCE,
    DOMAIN,
)

CONF_PRECISION_LIST = [
    selector.SelectOptionDict(value=str(PRECISION_TENTHS), label=str(PRECISION_TENTHS)),
    selector.SelectOptionDict(value=str(PRECISION_HALVES), label=str(PRECISION_HALVES)),
    selector.SelectOptionDict(value=str(PRECISION_WHOLE), label=str(PRECISION_WHOLE)),
]


class GenericThermostatConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Generic Thermostat."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the form(s)."""
        if user_input is None:
            return await self._async_step_basic()
        self.data = user_input
        return await self._async_show_advanced_settings({})

    async def async_step_advanced_settings(
        self, user_input: dict[str, Any] | None
    ) -> FlowResult:
        """Handle the advanced settings form."""
        if user_input is None:
            return await self._async_show_advanced_settings({})

        return self.async_create_entry(title=DEFAULT_NAME, data=self.data)

    async def _async_step_basic(self) -> FlowResult:
        """Handle the basic needed settings."""
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

    async def _async_show_advanced_settings(
        self, user_input: dict[str, Any]
    ) -> FlowResult:
        """Show the advanced settings form."""
        if user_input is None:
            user_input = {}
        return self.async_show_form(
            step_id="advanced_settings",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_AC_MODE): bool,
                    vol.Optional(CONF_MAX_TEMP): float,
                    vol.Optional(CONF_MIN_TEMP): float,
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
            ),
        )
