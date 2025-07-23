"""Setup config flow for Actron Neo integration."""

from typing import Any

from actron_neo_api import ActronNeoAPI, ActronNeoAuthError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN

from .const import _LOGGER, DOMAIN


class ActronNeoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Actron Air Neo."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._api: ActronNeoAPI = None
        self._device_code: str | None = None
        self._user_code: str = ""
        self._verification_uri: str = ""
        self._expires_minutes: str = "30"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if self._api is not None and self._device_code is not None:
            try:
                token_data = await self._api.poll_for_token(self._device_code)
            except ActronNeoAuthError as err:
                _LOGGER.error("Error checking authorization: %s", err)
                errors["base"] = "oauth2_error"

            if token_data is None:
                errors["base"] = "authorization_pending"
            else:
                user_data = await self._api.get_user_info()
                await self.async_set_unique_id(user_data["id"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_data["email"],
                    data={
                        CONF_API_TOKEN: self._api.refresh_token_value,
                    },
                )

        else:
            try:
                self._api = ActronNeoAPI()
                device_code_response = await self._api.request_device_code()

            except ActronNeoAuthError as err:
                _LOGGER.error("OAuth2 flow failed: %s", err)
                return self.async_abort(reason="oauth2_error")

            self._device_code = device_code_response["device_code"]
            self._user_code = device_code_response["user_code"]
            self._verification_uri = device_code_response["verification_uri_complete"]
            self._expires_minutes = str(device_code_response["expires_in"] // 60)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={
                "user_code": self._user_code,
                "verification_uri": self._verification_uri,
                "expires_minutes": self._expires_minutes,
            },
        )
