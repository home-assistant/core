"""Config flow for Jewish calendar integration."""

from __future__ import annotations

import logging
from typing import Any, get_args
import zoneinfo

from hdate.translator import Language
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_ELEVATION,
    CONF_LANGUAGE,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_TIME_ZONE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    LanguageSelector,
    LanguageSelectorConfig,
    LocationSelector,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import (
    CONF_CANDLE_LIGHT_MINUTES,
    CONF_DIASPORA,
    CONF_HAVDALAH_OFFSET_MINUTES,
    DEFAULT_CANDLE_LIGHT,
    DEFAULT_DIASPORA,
    DEFAULT_HAVDALAH_OFFSET_MINUTES,
    DEFAULT_LANGUAGE,
    DEFAULT_NAME,
    DOMAIN,
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_CANDLE_LIGHT_MINUTES, default=DEFAULT_CANDLE_LIGHT): int,
        vol.Optional(
            CONF_HAVDALAH_OFFSET_MINUTES, default=DEFAULT_HAVDALAH_OFFSET_MINUTES
        ): int,
    }
)


_LOGGER = logging.getLogger(__name__)


async def _get_data_schema(hass: HomeAssistant) -> vol.Schema:
    default_location = {
        CONF_LATITUDE: hass.config.latitude,
        CONF_LONGITUDE: hass.config.longitude,
    }
    get_timezones: list[str] = list(
        await hass.async_add_executor_job(zoneinfo.available_timezones)
    )
    return vol.Schema(
        {
            vol.Required(CONF_DIASPORA, default=DEFAULT_DIASPORA): BooleanSelector(),
            vol.Required(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): LanguageSelector(
                LanguageSelectorConfig(languages=list(get_args(Language)))
            ),
            vol.Optional(CONF_LOCATION, default=default_location): LocationSelector(),
            vol.Optional(CONF_ELEVATION, default=hass.config.elevation): int,
            vol.Optional(CONF_TIME_ZONE, default=hass.config.time_zone): SelectSelector(
                SelectSelectorConfig(options=get_timezones, sort=True)
            ),
        }
    )


class JewishCalendarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Jewish calendar."""

    VERSION = 3

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> JewishCalendarOptionsFlowHandler:
        """Get the options flow for this handler."""
        return JewishCalendarOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            if CONF_LOCATION in user_input:
                user_input[CONF_LATITUDE] = user_input[CONF_LOCATION][CONF_LATITUDE]
                user_input[CONF_LONGITUDE] = user_input[CONF_LOCATION][CONF_LONGITUDE]
            return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                await _get_data_schema(self.hass), user_input
            ),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        reconfigure_entry = self._get_reconfigure_entry()
        if not user_input:
            return self.async_show_form(
                data_schema=self.add_suggested_values_to_schema(
                    await _get_data_schema(self.hass),
                    reconfigure_entry.data,
                ),
                step_id="reconfigure",
            )

        return self.async_update_reload_and_abort(reconfigure_entry, data=user_input)


class JewishCalendarOptionsFlowHandler(OptionsFlow):
    """Handle Jewish Calendar options."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Manage the Jewish Calendar options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
