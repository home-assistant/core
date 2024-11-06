"""Config flow for Waze Travel Time integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME, CONF_REGION
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .const import (
    CONF_AVOID_FERRIES,
    CONF_AVOID_SUBSCRIPTION_ROADS,
    CONF_AVOID_TOLL_ROADS,
    CONF_DESTINATION,
    CONF_EXCL_FILTER,
    CONF_INCL_FILTER,
    CONF_ORIGIN,
    CONF_REALTIME,
    CONF_UNITS,
    CONF_VEHICLE_TYPE,
    DEFAULT_FILTER,
    DEFAULT_NAME,
    DEFAULT_OPTIONS,
    DOMAIN,
    IMPERIAL_UNITS,
    REGIONS,
    UNITS,
    VEHICLE_TYPES,
)
from .helpers import is_valid_config_entry

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_INCL_FILTER): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                multiple=True,
            ),
        ),
        vol.Optional(CONF_EXCL_FILTER): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                multiple=True,
            ),
        ),
        vol.Optional(CONF_REALTIME): BooleanSelector(),
        vol.Required(CONF_VEHICLE_TYPE): SelectSelector(
            SelectSelectorConfig(
                options=VEHICLE_TYPES,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_VEHICLE_TYPE,
                sort=True,
            )
        ),
        vol.Required(CONF_UNITS): SelectSelector(
            SelectSelectorConfig(
                options=UNITS,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_UNITS,
                sort=True,
            )
        ),
        vol.Optional(CONF_AVOID_TOLL_ROADS): BooleanSelector(),
        vol.Optional(CONF_AVOID_SUBSCRIPTION_ROADS): BooleanSelector(),
        vol.Optional(CONF_AVOID_FERRIES): BooleanSelector(),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
        vol.Required(CONF_ORIGIN): TextSelector(),
        vol.Required(CONF_DESTINATION): TextSelector(),
        vol.Required(CONF_REGION): SelectSelector(
            SelectSelectorConfig(
                options=REGIONS,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_REGION,
                sort=True,
            )
        ),
    }
)


def default_options(hass: HomeAssistant) -> dict[str, str | bool | list[str]]:
    """Get the default options."""
    defaults = DEFAULT_OPTIONS.copy()
    if hass.config.units is US_CUSTOMARY_SYSTEM:
        defaults[CONF_UNITS] = IMPERIAL_UNITS
    return defaults


class WazeOptionsFlow(OptionsFlow):
    """Handle an options flow for Waze Travel Time."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize waze options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            if user_input.get(CONF_INCL_FILTER) is None:
                user_input[CONF_INCL_FILTER] = DEFAULT_FILTER
            if user_input.get(CONF_EXCL_FILTER) is None:
                user_input[CONF_EXCL_FILTER] = DEFAULT_FILTER
            return self.async_create_entry(
                title="",
                data=user_input,
            )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )


class WazeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Waze Travel Time."""

    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> WazeOptionsFlow:
        """Get the options flow for this handler."""
        return WazeOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        user_input = user_input or {}

        if user_input:
            user_input[CONF_REGION] = user_input[CONF_REGION].upper()
            if await is_valid_config_entry(
                self.hass,
                user_input[CONF_ORIGIN],
                user_input[CONF_DESTINATION],
                user_input[CONF_REGION],
            ):
                if self.source == SOURCE_RECONFIGURE:
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        title=user_input[CONF_NAME],
                        data=user_input,
                    )
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, DEFAULT_NAME),
                    data=user_input,
                    options=default_options(self.hass),
                )

            # If we get here, it's because we couldn't connect
            errors["base"] = "cannot_connect"
            user_input[CONF_REGION] = user_input[CONF_REGION].lower()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(CONFIG_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        data = self._get_reconfigure_entry().data.copy()
        data[CONF_REGION] = data[CONF_REGION].lower()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(CONFIG_SCHEMA, data),
        )
