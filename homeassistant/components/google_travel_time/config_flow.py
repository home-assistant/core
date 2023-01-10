"""Config flow for Google Maps Travel Time integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_MODE, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .const import (
    ALL_LANGUAGES,
    ARRIVAL_TIME,
    AVOID,
    CONF_ARRIVAL_TIME,
    CONF_AVOID,
    CONF_DEPARTURE_TIME,
    CONF_DESTINATION,
    CONF_LANGUAGE,
    CONF_ORIGIN,
    CONF_TIME,
    CONF_TIME_TYPE,
    CONF_TRAFFIC_MODEL,
    CONF_TRANSIT_MODE,
    CONF_TRANSIT_ROUTING_PREFERENCE,
    CONF_UNITS,
    DEFAULT_NAME,
    DEPARTURE_TIME,
    DOMAIN,
    TIME_TYPES,
    TRANSIT_PREFS,
    TRANSPORT_TYPE,
    TRAVEL_MODE,
    TRAVEL_MODEL,
    UNITS,
    UNITS_IMPERIAL,
    UNITS_METRIC,
)
from .helpers import InvalidApiKeyException, UnknownException, validate_config_entry


def default_options(hass: HomeAssistant) -> dict[str, str | None]:
    """Get the default options."""
    return {
        CONF_MODE: "driving",
        CONF_UNITS: (
            UNITS_IMPERIAL if hass.config.units is US_CUSTOMARY_SYSTEM else UNITS_METRIC
        ),
    }


class GoogleOptionsFlow(config_entries.OptionsFlow):
    """Handle an options flow for Google Travel Time."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize google options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            time_type = user_input.pop(CONF_TIME_TYPE)
            if time := user_input.pop(CONF_TIME, None):
                if time_type == ARRIVAL_TIME:
                    user_input[CONF_ARRIVAL_TIME] = time
                else:
                    user_input[CONF_DEPARTURE_TIME] = time
            return self.async_create_entry(
                title="",
                data={k: v for k, v in user_input.items() if v not in (None, "")},
            )

        if CONF_ARRIVAL_TIME in self.config_entry.options:
            default_time_type = ARRIVAL_TIME
            default_time = self.config_entry.options[CONF_ARRIVAL_TIME]
        else:
            default_time_type = DEPARTURE_TIME
            default_time = self.config_entry.options.get(CONF_ARRIVAL_TIME, "")

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_MODE, default=self.config_entry.options[CONF_MODE]
                    ): vol.In(TRAVEL_MODE),
                    vol.Optional(
                        CONF_LANGUAGE,
                        default=self.config_entry.options.get(CONF_LANGUAGE),
                    ): vol.In([None, *ALL_LANGUAGES]),
                    vol.Optional(
                        CONF_AVOID, default=self.config_entry.options.get(CONF_AVOID)
                    ): vol.In([None, *AVOID]),
                    vol.Optional(
                        CONF_UNITS, default=self.config_entry.options[CONF_UNITS]
                    ): vol.In(UNITS),
                    vol.Optional(CONF_TIME_TYPE, default=default_time_type): vol.In(
                        TIME_TYPES
                    ),
                    vol.Optional(CONF_TIME, default=default_time): cv.string,
                    vol.Optional(
                        CONF_TRAFFIC_MODEL,
                        default=self.config_entry.options.get(CONF_TRAFFIC_MODEL),
                    ): vol.In([None, *TRAVEL_MODEL]),
                    vol.Optional(
                        CONF_TRANSIT_MODE,
                        default=self.config_entry.options.get(CONF_TRANSIT_MODE),
                    ): vol.In([None, *TRANSPORT_TYPE]),
                    vol.Optional(
                        CONF_TRANSIT_ROUTING_PREFERENCE,
                        default=self.config_entry.options.get(
                            CONF_TRANSIT_ROUTING_PREFERENCE
                        ),
                    ): vol.In([None, *TRANSIT_PREFS]),
                }
            ),
        )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Google Maps Travel Time."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> GoogleOptionsFlow:
        """Get the options flow for this handler."""
        return GoogleOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        user_input = user_input or {}
        if user_input:
            try:
                await self.hass.async_add_executor_job(
                    validate_config_entry,
                    self.hass,
                    user_input[CONF_API_KEY],
                    user_input[CONF_ORIGIN],
                    user_input[CONF_DESTINATION],
                )
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, DEFAULT_NAME),
                    data=user_input,
                    options=default_options(self.hass),
                )
            except InvalidApiKeyException:
                errors["base"] = "invalid_auth"
            except UnknownException:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)
                    ): cv.string,
                    vol.Required(CONF_API_KEY): cv.string,
                    vol.Required(CONF_DESTINATION): cv.string,
                    vol.Required(CONF_ORIGIN): cv.string,
                }
            ),
            errors=errors,
        )
