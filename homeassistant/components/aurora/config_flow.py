"""Config flow for SpaceX Launches and Starman."""
from __future__ import annotations

import logging

from aiohttp import ClientError
from auroranoaa import AuroraForecast
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)

from .const import CONF_THRESHOLD, DEFAULT_NAME, DEFAULT_THRESHOLD, DOMAIN

_LOGGER = logging.getLogger(__name__)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_THRESHOLD, default=DEFAULT_THRESHOLD): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=100)
        ),
    }
)
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA),
}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NOAA Aurora Integration."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SchemaOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            name = user_input[CONF_NAME]
            longitude = user_input[CONF_LONGITUDE]
            latitude = user_input[CONF_LATITUDE]

            session = aiohttp_client.async_get_clientsession(self.hass)
            api = AuroraForecast(session=session)

            try:
                await api.get_forecast_data(longitude, latitude)
            except ClientError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    f"{user_input[CONF_LONGITUDE]}_{user_input[CONF_LATITUDE]}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Aurora - {name}", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_NAME): str,
                        vol.Required(CONF_LONGITUDE): cv.longitude,
                        vol.Required(CONF_LATITUDE): cv.latitude,
                    }
                ),
                {
                    CONF_NAME: DEFAULT_NAME,
                    CONF_LONGITUDE: self.hass.config.longitude,
                    CONF_LATITUDE: self.hass.config.latitude,
                },
            ),
            errors=errors,
        )
