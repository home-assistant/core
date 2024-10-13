"""Adds config flow for Trafikverket Camera integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pytrafikverket.exceptions import InvalidAuthentication, NoCameraFound, UnknownError
from pytrafikverket.models import CameraInfoModel
from pytrafikverket.trafikverket_camera import TrafikverketCamera
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_ID, CONF_LOCATION
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import DOMAIN


class TVCameraConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Trafikverket Camera integration."""

    VERSION = 3

    cameras: list[CameraInfoModel]
    api_key: str

    async def validate_input(
        self, sensor_api: str, location: str
    ) -> tuple[dict[str, str], list[CameraInfoModel] | None]:
        """Validate input from user input."""
        errors: dict[str, str] = {}
        cameras: list[CameraInfoModel] | None = None

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

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication with Trafikverket."""

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication with Trafikverket."""
        errors: dict[str, str] = {}

        if user_input:
            api_key = user_input[CONF_API_KEY]

            reauth_entry = self._get_reauth_entry()
            errors, _ = await self.validate_input(api_key, reauth_entry.data[CONF_ID])

            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates={CONF_API_KEY: api_key}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): TextSelector(),
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-configuration with Trafikverket."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

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
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    unique_id=f"{DOMAIN}-{cameras[0].camera_id}",
                    title=cameras[0].camera_name or "Trafikverket Camera",
                    data={CONF_API_KEY: api_key, CONF_ID: cameras[0].camera_id},
                )

        schema = self.add_suggested_values_to_schema(
            vol.Schema(
                {
                    vol.Required(CONF_API_KEY): TextSelector(),
                    vol.Required(CONF_LOCATION): TextSelector(),
                }
            ),
            {**reconfigure_entry.data, **(user_input or {})},
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
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
    ) -> ConfigFlowResult:
        """Handle when multiple cameras."""

        if user_input:
            errors, cameras = await self.validate_input(
                self.api_key, user_input[CONF_ID]
            )

            if not errors and cameras:
                if self.source == SOURCE_RECONFIGURE:
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        unique_id=f"{DOMAIN}-{cameras[0].camera_id}",
                        title=cameras[0].camera_name or "Trafikverket Camera",
                        data={
                            CONF_API_KEY: self.api_key,
                            CONF_ID: cameras[0].camera_id,
                        },
                    )
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
