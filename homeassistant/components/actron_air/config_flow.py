"""Setup config flow for Actron Air integration."""

import asyncio
from typing import Any

from actron_neo_api import ActronNeoAPI, ActronNeoAuthError

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN
from homeassistant.exceptions import HomeAssistantError

from .const import _LOGGER, DOMAIN


class ActronAirConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Actron Air."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._api: ActronNeoAPI | None = None
        self._device_code: str | None = None
        self._user_code: str = ""
        self._verification_uri: str = ""
        self._expires_minutes: str = "30"
        self.login_task: asyncio.Task | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if self._api is None:
            _LOGGER.debug("Initiating device authorization")
            self._api = ActronNeoAPI()
            try:
                device_code_response = await self._api.request_device_code()
            except ActronNeoAuthError as err:
                _LOGGER.error("OAuth2 flow failed: %s", err)
                return self.async_abort(reason="oauth2_error")

            self._device_code = device_code_response["device_code"]
            self._user_code = device_code_response["user_code"]
            self._verification_uri = device_code_response["verification_uri_complete"]
            self._expires_minutes = str(device_code_response["expires_in"] // 60)

        async def _wait_for_authorization() -> None:
            """Wait for the user to authorize the device."""
            assert self._api is not None
            assert self._device_code is not None
            _LOGGER.debug("Waiting for device authorization")
            try:
                await self._api.poll_for_token(self._device_code)
                _LOGGER.debug("Authorization successful")
            except ActronNeoAuthError as ex:
                _LOGGER.exception("Error while waiting for device authorization")
                raise CannotConnect from ex

        _LOGGER.debug("Checking login task")
        if self.login_task is None:
            _LOGGER.debug("Creating task for device authorization")
            self.login_task = self.hass.async_create_task(_wait_for_authorization())

        if self.login_task.done():
            _LOGGER.debug("Login task is done, checking results")
            if exception := self.login_task.exception():
                if isinstance(exception, CannotConnect):
                    return self.async_show_progress_done(
                        next_step_id="connection_error"
                    )
                return self.async_show_progress_done(next_step_id="timeout")
            return self.async_show_progress_done(next_step_id="finish_login")

        return self.async_show_progress(
            step_id="user",
            progress_action="wait_for_authorization",
            description_placeholders={
                "user_code": self._user_code,
                "verification_uri": self._verification_uri,
                "expires_minutes": self._expires_minutes,
            },
            progress_task=self.login_task,
        )

    async def async_step_finish_login(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the finalization of login."""
        _LOGGER.debug("Finalizing authorization")
        assert self._api is not None

        try:
            user_data = await self._api.get_user_info()
        except ActronNeoAuthError as err:
            _LOGGER.error("Error getting user info: %s", err)
            return self.async_abort(reason="oauth2_error")

        unique_id = str(user_data["id"])
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=user_data["email"],
            data={CONF_API_TOKEN: self._api.refresh_token_value},
        )

    async def async_step_timeout(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle issues that need transition await from progress step."""
        if user_input is None:
            return self.async_show_form(
                step_id="timeout",
            )
        del self.login_task
        return await self.async_step_user()

    async def async_step_connection_error(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle connection error from progress step."""
        if user_input is None:
            return self.async_show_form(step_id="connection_error")

        # Reset state and try again
        self._api = None
        self._device_code = None
        self.login_task = None
        return await self.async_step_user()


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
