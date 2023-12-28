"""Adds config flow for AccuWeather."""
from __future__ import annotations

import asyncio
from asyncio import timeout
from typing import Any

from accuweather import AccuWeather, ApiError, InvalidApiKeyError, RequestsExceededError
from aiohttp import ClientError
from aiohttp.client_exceptions import ClientConnectorError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)

from .const import CONF_FORECAST, DOMAIN

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_FORECAST, default=False): bool,
    }
)
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA),
}


class AccuWeatherFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for AccuWeather."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        # Under the terms of use of the API, one user can use one free API key. Due to
        # the small number of requests allowed, we only allow one integration instance.
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors = {}

        if user_input is not None:
            websession = async_get_clientsession(self.hass)
            try:
                async with timeout(10):
                    accuweather = AccuWeather(
                        user_input[CONF_API_KEY],
                        websession,
                        latitude=user_input[CONF_LATITUDE],
                        longitude=user_input[CONF_LONGITUDE],
                    )
                    await accuweather.async_get_location()
            except (ApiError, ClientConnectorError, asyncio.TimeoutError, ClientError):
                errors["base"] = "cannot_connect"
            except InvalidApiKeyError:
                errors[CONF_API_KEY] = "invalid_api_key"
            except RequestsExceededError:
                errors[CONF_API_KEY] = "requests_exceeded"
            else:
                await self.async_set_unique_id(
                    accuweather.location_key, raise_on_progress=False
                )

                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Optional(
                        CONF_LATITUDE, default=self.hass.config.latitude
                    ): cv.latitude,
                    vol.Optional(
                        CONF_LONGITUDE, default=self.hass.config.longitude
                    ): cv.longitude,
                    vol.Optional(
                        CONF_NAME, default=self.hass.config.location_name
                    ): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SchemaOptionsFlowHandler:
        """Options callback for AccuWeather."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)
