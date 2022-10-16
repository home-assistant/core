"""Config flow for generic Thermostat."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.climate import (
    PRESET_ACTIVITY,
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_HOME,
    PRESET_SLEEP,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import (
    CONF_NAME,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TimeSelector,
)

from .consts import (
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
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DEFAULT_NAME,
    DEFAULT_TOLERANCE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


HVAC_MODE = [
    SelectOptionDict(value=HVACMode.COOL, label=HVACMode.COOL),
    SelectOptionDict(value=HVACMode.HEAT, label=HVACMode.HEAT),
    SelectOptionDict(value=HVACMode.OFF, label=HVACMode.OFF),
]

PRECISION = [
    SelectOptionDict(value=str(PRECISION_TENTHS), label=str(PRECISION_TENTHS)),
    SelectOptionDict(value=str(PRECISION_HALVES), label=str(PRECISION_HALVES)),
    SelectOptionDict(value=str(PRECISION_WHOLE), label=str(PRECISION_WHOLE)),
]


def build_schema(user_input: Mapping[str, Any], is_options_flow: bool = False):
    """Create schema for camera config setup."""
    spec = {
        vol.Optional(
            CONF_NAME,
            description={"suggested_value": user_input.get(CONF_NAME, DEFAULT_NAME)},
        ): TextSelector(),
        vol.Required(
            CONF_HEATER,
            description={"suggested_value": user_input.get(CONF_HEATER)},
        ): EntitySelector(),
        vol.Required(
            CONF_SENSOR,
            description={"suggested_value": user_input.get(CONF_SENSOR)},
        ): EntitySelector(),
        vol.Optional(
            CONF_MAX_TEMP,
            description={
                "suggested_value": user_input.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP)
            },
        ): NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, step=0.1)),
        vol.Optional(
            CONF_MIN_TEMP,
            description={
                "suggested_value": user_input.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP)
            },
        ): NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, step=0.1)),
        vol.Optional(
            CONF_AC_MODE,
            description={"suggested_value": user_input.get(CONF_AC_MODE)},
        ): BooleanSelector(),
        vol.Optional(
            CONF_MIN_DUR,
            description={"suggested_value": user_input.get(CONF_MIN_DUR)},
        ): TimeSelector(),
        vol.Optional(
            CONF_COLD_TOLERANCE,
            description={
                "suggested_value": user_input.get(
                    CONF_COLD_TOLERANCE, DEFAULT_TOLERANCE
                )
            },
        ): NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, step=0.1)),
        vol.Optional(
            CONF_HOT_TOLERANCE,
            default=DEFAULT_TOLERANCE,
            description={
                "suggested_value": user_input.get(CONF_HOT_TOLERANCE, DEFAULT_TOLERANCE)
            },
        ): NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, step=0.1)),
        vol.Optional(
            CONF_TARGET_TEMP,
            description={"suggested_value": user_input.get(CONF_TARGET_TEMP)},
        ): NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, step=0.1)),
        vol.Optional(
            CONF_KEEP_ALIVE,
            description={"suggested_value": user_input.get(CONF_KEEP_ALIVE)},
        ): TimeSelector(),
        vol.Optional(
            CONF_INITIAL_HVAC_MODE,
            description={"suggested_value": user_input.get(CONF_INITIAL_HVAC_MODE)},
        ): SelectSelector(
            SelectSelectorConfig(options=HVAC_MODE, mode=SelectSelectorMode.DROPDOWN)
        ),
        vol.Optional(
            CONF_PRECISION,
            description={"suggested_value": user_input.get(CONF_PRECISION)},
        ): SelectSelector(
            SelectSelectorConfig(options=PRECISION, mode=SelectSelectorMode.DROPDOWN)
        ),
        vol.Optional(
            CONF_TEMP_STEP,
            description={"suggested_value": user_input.get(CONF_TEMP_STEP)},
        ): SelectSelector(
            SelectSelectorConfig(options=PRECISION, mode=SelectSelectorMode.DROPDOWN)
        ),
        vol.Optional(
            f"{PRESET_AWAY}_temp",
            description={"suggested_value": user_input.get(f"{PRESET_AWAY}_temp")},
        ): NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, step=0.1)),
        vol.Optional(
            f"{PRESET_COMFORT}_temp",
            description={"suggested_value": user_input.get(f"{PRESET_COMFORT}_temp")},
        ): NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, step=0.1)),
        vol.Optional(
            f"{PRESET_HOME}_temp",
            description={"suggested_value": user_input.get(f"{PRESET_HOME}_temp")},
        ): NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, step=0.1)),
        vol.Optional(
            f"{PRESET_SLEEP}_temp",
            description={"suggested_value": user_input.get(f"{PRESET_SLEEP}_temp")},
        ): NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, step=0.1)),
        vol.Optional(
            f"{PRESET_ACTIVITY}_temp",
            description={"suggested_value": user_input.get(f"{PRESET_ACTIVITY}_temp")},
        ): NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, step=0.1)),
    }

    if is_options_flow:
        spec.pop(CONF_NAME)

    return vol.Schema(spec)


class GenericThermostatConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for generic Thermostat."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get option flow."""
        return GenericThermostatOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the start of the config flow."""
        if user_input:
            self._async_abort_entries_match(
                {
                    CONF_HEATER: user_input[CONF_HEATER],
                    CONF_SENSOR: user_input[CONF_SENSOR],
                }
            )
            return self.async_create_entry(
                title=user_input.get(CONF_NAME, DEFAULT_NAME),
                data={},
                options=user_input,
            )

        user_input = {}

        return self.async_show_form(
            step_id="user", data_schema=build_schema(user_input)
        )

    async def async_step_import(self, import_config: dict[str, str]) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        if keep_alive := import_config.get(CONF_KEEP_ALIVE):
            import_config[CONF_KEEP_ALIVE] = str(
                datetime.strptime(str(keep_alive), "%H:%M:%S").time()
            )
        if min_dur := import_config.get(CONF_MIN_DUR):
            import_config[CONF_MIN_DUR] = str(
                datetime.strptime(str(min_dur), "%H:%M:%S").time()
            )
        return await self.async_step_user(import_config)


class GenericThermostatOptionsFlowHandler(OptionsFlow):
    """Handle option."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Init object."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Handle a flow initialized by the user."""
        if user_input:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init", data_schema=build_schema(self.config_entry.options, True)
        )
