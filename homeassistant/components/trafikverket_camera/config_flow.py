"""Adds config flow for Trafikverket Camera integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pytrafikverket.trafikverket_camera import TrafikverketCamera
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import CONF_LOCATION, DOMAIN


class TVCameraConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Trafikverket Camera integration."""

    VERSION = 1

    entry: config_entries.ConfigEntry | None

    async def validate_input(self, sensor_api: str, location: str) -> None:
        """Validate input from user input."""
        web_session = async_get_clientsession(self.hass)
        camera_api = TrafikverketCamera(web_session, sensor_api)
        await camera_api.async_get_camera(location)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle re-authentication with Trafikverket."""

        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm re-authentication with Trafikverket."""
        errors: dict[str, str] = {}

        if user_input:
            api_key = user_input[CONF_API_KEY]

            assert self.entry is not None
            try:
                await self.validate_input(api_key, self.entry.data[CONF_LOCATION])
            except ValueError as error:
                errors["base"] = "cannot_connect"
                if "Invalid authentication" in str(error):
                    errors["base"] = "invalid_auth"
                if "Could not find a camera with the specified name" in str(error):
                    errors["base"] = "invalid_location"
                if "Found multiple camera with the specified name" in str(error):
                    errors["base"] = "more_locations"
            else:
                self.hass.config_entries.async_update_entry(
                    self.entry,
                    data={
                        **self.entry.data,
                        CONF_API_KEY: api_key,
                    },
                )
                await self.hass.config_entries.async_reload(self.entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): cv.string,
                }
            ),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            location = user_input[CONF_LOCATION]

            try:
                await self.validate_input(api_key, location)
            except ValueError as error:
                errors["base"] = "cannot_connect"
                if "Invalid authentication" in str(error):
                    errors["base"] = "invalid_auth"
                if "Could not find a camera with the specified name" in str(error):
                    errors["base"] = "invalid_location"
                if "Found multiple camera with the specified name" in str(error):
                    errors["base"] = "more_locations"

            else:
                await self.async_set_unique_id(f"{DOMAIN}-{location}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_LOCATION],
                    data={
                        CONF_API_KEY: api_key,
                        CONF_LOCATION: location,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): cv.string,
                    vol.Required(CONF_LOCATION): cv.string,
                }
            ),
            errors=errors,
        )
