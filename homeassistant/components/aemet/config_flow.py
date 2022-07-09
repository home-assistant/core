"""Config flow for AEMET OpenData."""
from __future__ import annotations

from aemet_opendata import AEMET
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import CONF_STATION_UPDATES, DEFAULT_NAME, DOMAIN


class AemetConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for AEMET OpenData."""

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            latitude = user_input[CONF_LATITUDE]
            longitude = user_input[CONF_LONGITUDE]

            await self.async_set_unique_id(f"{latitude}-{longitude}")
            self._abort_if_unique_id_configured()

            api_online = await _is_aemet_api_online(self.hass, user_input[CONF_API_KEY])
            if not api_online:
                errors["base"] = "invalid_api_key"

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY): str,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Optional(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): cv.latitude,
                vol.Optional(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): cv.longitude,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for AEMET."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_STATION_UPDATES,
                    default=self.config_entry.options.get(CONF_STATION_UPDATES),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)


async def _is_aemet_api_online(hass, api_key):
    aemet = AEMET(api_key)
    return await hass.async_add_executor_job(
        aemet.get_conventional_observation_stations, False
    )
