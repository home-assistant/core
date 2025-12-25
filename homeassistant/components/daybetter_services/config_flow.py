"""Config flow for DayBetter Services integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from daybetter_python import APIError, AuthenticationError, DayBetterClient
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_TOKEN, CONF_USER_CODE, DOMAIN


class DayBetterServicesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DayBetter Services."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._reauth_entry: ConfigEntry | None = None
        self._reauth_user_code: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        default_user_code = user_input[CONF_USER_CODE] if user_input else ""
        return await self._async_handle_step(
            user_input,
            step_id="user",
            default_user_code=default_user_code,
            is_reauth=False,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle the start of the re-authentication flow."""
        self._reauth_entry = self._get_reauth_entry()
        self._reauth_user_code = entry_data.get(CONF_USER_CODE, "")
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the re-authentication confirmation step."""
        return await self._async_handle_step(
            user_input,
            step_id="reauth_confirm",
            default_user_code=self._reauth_user_code,
            is_reauth=True,
        )

    async def _async_handle_step(
        self,
        user_input: dict[str, Any] | None,
        *,
        step_id: str,
        default_user_code: str,
        is_reauth: bool,
    ) -> ConfigFlowResult:
        """Validate user input and either create or update the entry."""

        errors: dict[str, str] = {}
        current_user_code = default_user_code

        if user_input is not None:
            current_user_code = user_input[CONF_USER_CODE]
            try:
                data = await self._async_validate_credentials(current_user_code)
            except InvalidCode:
                errors["base"] = "invalid_code"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                if is_reauth:
                    entry = self._reauth_entry
                    assert entry is not None
                    return self.async_update_reload_and_abort(entry, data=data)
                return self.async_create_entry(title="DayBetter Services", data=data)

        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(
                {vol.Required(CONF_USER_CODE, default=current_user_code): str}
            ),
            errors=errors,
            description_placeholders={
                "docs_url": "https://www.home-assistant.io/integrations/daybetter_services"
            },
        )

    async def _async_validate_credentials(self, user_code: str) -> dict[str, str]:
        """Validate user code and return entry data."""
        client = DayBetterClient(token="")
        client_with_token: DayBetterClient | None = None
        try:
            try:
                integrate_result = await client.integrate(user_code)
            except (AuthenticationError, APIError) as err:
                raise CannotConnect from err

            if (
                not integrate_result
                or integrate_result.get("code") != 1
                or "data" not in integrate_result
                or "hassCodeToken" not in integrate_result["data"]
            ):
                raise InvalidCode

            token = integrate_result["data"]["hassCodeToken"]

            client_with_token = DayBetterClient(token=token)
            try:
                await client_with_token.fetch_devices()
                await client_with_token.fetch_pids()
            except (AuthenticationError, APIError) as err:
                raise CannotConnect from err
        finally:
            await client.close()
            if client_with_token is not None:
                await client_with_token.close()

        return {
            CONF_USER_CODE: user_code,
            CONF_TOKEN: token,
        }


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidCode(HomeAssistantError):
    """Error to indicate invalid user code."""
