"""Adds config flow for Trafikverket Camera integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pytrafikverket.exceptions import (
    InvalidAuthentication,
    MultipleCamerasFound,
    NoCameraFound,
    UnknownError,
)
from pytrafikverket.trafikverket_camera import CameraInfo, TrafikverketCamera
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

    async def validate_input(
        self, sensor_api: str, location: str
    ) -> tuple[dict[str, str], str | None]:
        """Validate input from user input."""
        errors: dict[str, str] = {}
        camera_info: CameraInfo | None = None

        web_session = async_get_clientsession(self.hass)
        camera_api = TrafikverketCamera(web_session, sensor_api)
        try:
            camera_info = await camera_api.async_get_camera(location)
        except NoCameraFound:
            errors["location"] = "invalid_location"
        except MultipleCamerasFound:
            errors["location"] = "more_locations"
        except InvalidAuthentication:
            errors["base"] = "invalid_auth"
        except UnknownError:
            errors["base"] = "cannot_connect"

        camera_location = camera_info.location if camera_info else None
        return (errors, camera_location)

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
            errors, _ = await self.validate_input(
                api_key, self.entry.data[CONF_LOCATION]
            )

            if not errors:
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
        errors: dict[str, str] = {}

        if user_input:
            api_key = user_input[CONF_API_KEY]
            location = user_input[CONF_LOCATION]

            errors, camera_location = await self.validate_input(api_key, location)

            if not errors:
                assert camera_location
                await self.async_set_unique_id(f"{DOMAIN}-{camera_location}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=camera_location,
                    data={
                        CONF_API_KEY: api_key,
                        CONF_LOCATION: camera_location,
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
