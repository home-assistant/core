"""Config flow for Jewish calendar integration."""

from __future__ import annotations

import logging
from typing import Any
import zoneinfo

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithConfigEntry,
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
    LocationSelector,
    SelectOptionDict,
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

LANGUAGE = [
    SelectOptionDict(value="hebrew", label="Hebrew"),
    SelectOptionDict(value="english", label="English"),
]

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_CANDLE_LIGHT_MINUTES, default=DEFAULT_CANDLE_LIGHT): int,
        vol.Optional(
            CONF_HAVDALAH_OFFSET_MINUTES, default=DEFAULT_HAVDALAH_OFFSET_MINUTES
        ): int,
    }
)


_LOGGER = logging.getLogger(__name__)


def _get_data_schema(hass: HomeAssistant) -> vol.Schema:
    default_location = {
        CONF_LATITUDE: hass.config.latitude,
        CONF_LONGITUDE: hass.config.longitude,
    }
    return vol.Schema(
        {
            vol.Required(CONF_DIASPORA, default=DEFAULT_DIASPORA): BooleanSelector(),
            vol.Required(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): SelectSelector(
                SelectSelectorConfig(options=LANGUAGE)
            ),
            vol.Optional(CONF_LOCATION, default=default_location): LocationSelector(),
            vol.Optional(CONF_ELEVATION, default=hass.config.elevation): int,
            vol.Optional(CONF_TIME_ZONE, default=hass.config.time_zone): SelectSelector(
                SelectSelectorConfig(
                    options=sorted(zoneinfo.available_timezones()),
                )
            ),
        }
    )


class JewishCalendarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Jewish calendar."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowWithConfigEntry:
        """Get the options flow for this handler."""
        return JewishCalendarOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            _options = {}
            if CONF_CANDLE_LIGHT_MINUTES in user_input:
                _options[CONF_CANDLE_LIGHT_MINUTES] = user_input[
                    CONF_CANDLE_LIGHT_MINUTES
                ]
                del user_input[CONF_CANDLE_LIGHT_MINUTES]
            if CONF_HAVDALAH_OFFSET_MINUTES in user_input:
                _options[CONF_HAVDALAH_OFFSET_MINUTES] = user_input[
                    CONF_HAVDALAH_OFFSET_MINUTES
                ]
                del user_input[CONF_HAVDALAH_OFFSET_MINUTES]
            if CONF_LOCATION in user_input:
                user_input[CONF_LATITUDE] = user_input[CONF_LOCATION][CONF_LATITUDE]
                user_input[CONF_LONGITUDE] = user_input[CONF_LOCATION][CONF_LONGITUDE]
            return self.async_create_entry(
                title=DEFAULT_NAME, data=user_input, options=_options
            )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                _get_data_schema(self.hass), user_input
            ),
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_data)


class JewishCalendarOptionsFlowHandler(OptionsFlowWithConfigEntry):
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
