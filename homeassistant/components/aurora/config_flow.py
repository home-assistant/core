"""Config flow for Aurora."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError
from auroranoaa import AuroraForecast
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)

from .const import CONF_THRESHOLD, DEFAULT_THRESHOLD, DOMAIN

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


class AuroraConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NOAA Aurora Integration."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SchemaOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            longitude = user_input[CONF_LONGITUDE]
            latitude = user_input[CONF_LATITUDE]

            session = aiohttp_client.async_get_clientsession(self.hass)
            api = AuroraForecast(session=session)

            try:
                await api.get_forecast_data(longitude, latitude)
            except ClientError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    f"{user_input[CONF_LONGITUDE]}_{user_input[CONF_LATITUDE]}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Aurora visibility", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_LONGITUDE): cv.longitude,
                        vol.Required(CONF_LATITUDE): cv.latitude,
                    }
                ),
                {
                    CONF_LONGITUDE: self.hass.config.longitude,
                    CONF_LATITUDE: self.hass.config.latitude,
                },
            ),
            errors=errors,
        )
