"""Config flow to configure the Ambee integration."""
from __future__ import annotations

from typing import Any

from ambee import Ambee, AmbeeAuthenticationError, AmbeeError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN


class AmbeeFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Ambee."""

    VERSION = 1

    entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            try:
                client = Ambee(
                    api_key=user_input[CONF_API_KEY],
                    latitude=user_input[CONF_LATITUDE],
                    longitude=user_input[CONF_LONGITUDE],
                    session=session,
                )
                await client.air_quality()
            except AmbeeAuthenticationError:
                errors["base"] = "invalid_api_key"
            except AmbeeError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_LATITUDE: user_input[CONF_LATITUDE],
                        CONF_LONGITUDE: user_input[CONF_LONGITUDE],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Optional(
                        CONF_NAME, default=self.hass.config.location_name
                    ): str,
                    vol.Optional(
                        CONF_LATITUDE, default=self.hass.config.latitude
                    ): cv.latitude,
                    vol.Optional(
                        CONF_LONGITUDE, default=self.hass.config.longitude
                    ): cv.longitude,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, data: dict[str, Any]) -> FlowResult:
        """Handle initiation of re-authentication with Ambee."""
        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle re-authentication with Ambee."""
        errors = {}
        if user_input is not None and self.entry:
            session = async_get_clientsession(self.hass)
            client = Ambee(
                api_key=user_input[CONF_API_KEY],
                latitude=self.entry.data[CONF_LATITUDE],
                longitude=self.entry.data[CONF_LONGITUDE],
                session=session,
            )
            try:
                await client.air_quality()
            except AmbeeAuthenticationError:
                errors["base"] = "invalid_api_key"
            except AmbeeError:
                errors["base"] = "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(
                    self.entry,
                    data={
                        **self.entry.data,
                        CONF_API_KEY: user_input[CONF_API_KEY],
                    },
                )
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self.entry.entry_id)
                )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )
