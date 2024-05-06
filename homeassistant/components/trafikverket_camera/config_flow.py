"""Adds config flow for Trafikverket Camera integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pytrafikverket.exceptions import InvalidAuthentication, NoCameraFound, UnknownError
from pytrafikverket.trafikverket_camera import CameraInfo, TrafikverketCamera
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_ID, CONF_LOCATION
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import DOMAIN


class TVCameraConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Trafikverket Camera integration."""

    VERSION = 3

    entry: config_entries.ConfigEntry | None
    cameras: list[CameraInfo]
    api_key: str

    async def validate_input(
        self, sensor_api: str, location: str
    ) -> tuple[dict[str, str], list[CameraInfo] | None]:
        """Validate input from user input."""
        errors: dict[str, str] = {}
        cameras: list[CameraInfo] | None = None

        web_session = async_get_clientsession(self.hass)
        camera_api = TrafikverketCamera(web_session, sensor_api)
        try:
            cameras = await camera_api.async_get_cameras(location)
        except NoCameraFound:
            errors["location"] = "invalid_location"
        except InvalidAuthentication:
            errors["base"] = "invalid_auth"
        except UnknownError:
            errors["base"] = "cannot_connect"

        return (errors, cameras)

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
            errors, _ = await self.validate_input(api_key, self.entry.data[CONF_ID])

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
                    vol.Required(CONF_API_KEY): TextSelector(),
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

            errors, cameras = await self.validate_input(api_key, location)

            if not errors and cameras:
                if len(cameras) > 1:
                    self.cameras = cameras
                    self.api_key = api_key
                    return await self.async_step_multiple_cameras()
                await self.async_set_unique_id(f"{DOMAIN}-{cameras[0].camera_id}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=cameras[0].camera_name or "Trafikverket Camera",
                    data={CONF_API_KEY: api_key, CONF_ID: cameras[0].camera_id},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): TextSelector(),
                    vol.Required(CONF_LOCATION): TextSelector(),
                }
            ),
            errors=errors,
        )

    async def async_step_multiple_cameras(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle when multiple cameras."""

        if user_input:
            errors, cameras = await self.validate_input(
                self.api_key, user_input[CONF_ID]
            )

            if not errors and cameras:
                await self.async_set_unique_id(f"{DOMAIN}-{cameras[0].camera_id}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=cameras[0].camera_name or "Trafikverket Camera",
                    data={CONF_API_KEY: self.api_key, CONF_ID: cameras[0].camera_id},
                )

        camera_choices = [
            SelectOptionDict(
                value=f"{camera_info.camera_id}",
                label=f"{camera_info.camera_id} - {camera_info.camera_name} - {camera_info.location}",
            )
            for camera_info in self.cameras
        ]

        return self.async_show_form(
            step_id="multiple_cameras",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=camera_choices, mode=SelectSelectorMode.LIST
                        )
                    ),
                }
            ),
        )
