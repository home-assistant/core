"""Config flow for the Generic Thermostat integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.climate import (
    PRESET_ACTIVITY,
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_HOME,
    PRESET_SLEEP,
    HVACMode,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import PRECISION_HALVES, PRECISION_TENTHS, PRECISION_WHOLE
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)

from .climate import CONF_PRESETS
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
    str(PRECISION_TENTHS),
    str(PRECISION_HALVES),
    str(PRECISION_WHOLE),
]

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_AC_MODE, default=False): selector.BooleanSelector(),
        vol.Optional(CONF_MAX_TEMP): selector.NumberSelector(
            selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_MIN_TEMP, default=DEFAULT_MIN_TEMP): selector.NumberSelector(
            selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_MIN_DUR): selector.DurationSelector(
            selector.DurationSelectorConfig()
        ),
        vol.Optional(
            CONF_COLD_TOLERANCE, default=DEFAULT_TOLERANCE
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX)
        ),
        vol.Optional(
            CONF_HOT_TOLERANCE, default=DEFAULT_TOLERANCE
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_TARGET_TEMP): selector.NumberSelector(
            selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX)
        ),
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
        **{
            vol.Optional(CONF_PRESETS[preset]): vol.Coerce(float)
            for preset in (
                PRESET_AWAY,
                PRESET_COMFORT,
                PRESET_ECO,
                PRESET_HOME,
                PRESET_SLEEP,
                PRESET_ACTIVITY,
            )
        },
    }
)


OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA),
}

_LOGGER = logging.getLogger(__name__)


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

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
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

        self._async_abort_entries_match(
            {
                CONF_HEATER: user_input[CONF_HEATER],
                CONF_SENSOR: user_input[CONF_SENSOR],
            }
        )
        return self.async_create_entry(
            title=user_input[CONF_NAME], data=user_input, options=options
        )

    async def async_step_import(
        self, import_config: dict[str, Any]
    ) -> ConfigFlowResult:
        """Import a config entry from a configuration.yaml."""
        _LOGGER.debug("Importing Generic Thermostat from configuration.yaml")
        data: dict[str, Any] = {
            CONF_NAME: import_config[CONF_NAME],
            CONF_HEATER: import_config[CONF_HEATER],
            CONF_SENSOR: import_config[CONF_SENSOR],
        }
        options: dict[str, Any] = {
            CONF_MIN_TEMP: import_config[CONF_MIN_TEMP],
            CONF_MAX_TEMP: import_config[CONF_MAX_TEMP],
            CONF_AC_MODE: import_config[CONF_AC_MODE],
            CONF_MIN_DUR: import_config[CONF_MIN_DUR],
            CONF_COLD_TOLERANCE: import_config[CONF_COLD_TOLERANCE],
            CONF_HOT_TOLERANCE: import_config[CONF_HOT_TOLERANCE],
            CONF_KEEP_ALIVE: import_config[CONF_KEEP_ALIVE],
            CONF_INITIAL_HVAC_MODE: import_config[CONF_INITIAL_HVAC_MODE],
            CONF_PRECISION: str(import_config[CONF_PRECISION]),
            CONF_TEMP_STEP: str(import_config[CONF_TEMP_STEP]),
            CONF_TARGET_TEMP: import_config[CONF_TARGET_TEMP],
            **{
                CONF_PRESETS[p]: import_config.get(CONF_PRESETS[p])
                for p in CONF_PRESETS
                if import_config.get(CONF_PRESETS[p]) is not None
            },
        }
        return await self.async_step_user(user_input=data, options=options)
