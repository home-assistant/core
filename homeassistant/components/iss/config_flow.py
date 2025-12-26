"""Config flow to configure iss component."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_SHOW_ON_MAP
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_PEOPLE_UPDATE_HOURS,
    CONF_POSITION_UPDATE_SECONDS,
    CONF_TLE_SOURCES,
    DEFAULT_NAME,
    DEFAULT_PEOPLE_UPDATE_HOURS,
    DEFAULT_POSITION_UPDATE_SECONDS,
    DEFAULT_TLE_SOURCES,
    DOMAIN,
    MIN_PEOPLE_UPDATE_HOURS,
    MIN_POSITION_UPDATE_SECONDS,
    TLE_SOURCES,
)


class ISSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for iss component."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            return self.async_create_entry(
                title=DEFAULT_NAME,
                data={},
                options={
                    CONF_SHOW_ON_MAP: user_input.get(CONF_SHOW_ON_MAP, False),
                    CONF_TLE_SOURCES: DEFAULT_TLE_SOURCES,
                },
            )

        return self.async_show_form(step_id="user")


class OptionsFlowHandler(OptionsFlow):
    """Config flow options handler for iss."""

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SHOW_ON_MAP,
                    default=self.config_entry.options.get(CONF_SHOW_ON_MAP, False),
                ): bool,
                vol.Optional(
                    CONF_PEOPLE_UPDATE_HOURS,
                    default=self.config_entry.options.get(
                        CONF_PEOPLE_UPDATE_HOURS, DEFAULT_PEOPLE_UPDATE_HOURS
                    ),
                    description={"suffix": "hours"},
                ): int,
                vol.Optional(
                    CONF_POSITION_UPDATE_SECONDS,
                    default=self.config_entry.options.get(
                        CONF_POSITION_UPDATE_SECONDS, DEFAULT_POSITION_UPDATE_SECONDS
                    ),
                    description={"suffix": "seconds"},
                ): int,
                vol.Optional(
                    CONF_TLE_SOURCES,
                    default=self.config_entry.options.get(
                        CONF_TLE_SOURCES, DEFAULT_TLE_SOURCES
                    ),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(TLE_SOURCES.keys()),
                        multiple=True,
                        translation_key="tle_sources",
                    )
                ),
            }
        )

        if user_input is not None:
            # Validate TLE sources
            tle_sources = user_input.get(CONF_TLE_SOURCES, [])
            if not tle_sources:
                errors[CONF_TLE_SOURCES] = "no_tle_sources"
            elif not all(source in TLE_SOURCES for source in tle_sources):
                errors[CONF_TLE_SOURCES] = "invalid_tle_source"

            # Validate people update hours
            if user_input[CONF_PEOPLE_UPDATE_HOURS] < MIN_PEOPLE_UPDATE_HOURS:
                errors[CONF_PEOPLE_UPDATE_HOURS] = "min_people_update_hours"

            # Validate position update seconds
            if user_input[CONF_POSITION_UPDATE_SECONDS] < MIN_POSITION_UPDATE_SECONDS:
                errors[CONF_POSITION_UPDATE_SECONDS] = "min_position_update_seconds"

            # If no errors, create entry
            if not errors:
                return self.async_create_entry(
                    data=self.config_entry.options | user_input
                )

            # Show form again with errors
            return self.async_show_form(
                step_id="init",
                data_schema=data_schema,
                errors=errors,
            )

        return self.async_show_form(step_id="init", data_schema=data_schema)
