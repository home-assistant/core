"""Config flow for the VRChat integration."""

from typing import Any, Final, override

from aiohttp import ClientError
import probatio
import vrchatapi.exceptions
from vrchatapi.highlevel import TwoFactorAuthChallenge, TwoFactorAuthRequired, VRChatAPI

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_2FA_CODE, CONF_EMAIL_2FA_CODE, DOMAIN, USER_AGENT
from .store import InitialCurrentUserData, get_vrchat_auth_cookie_store


class VRChatConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for VRChat."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._api: VRChatAPI | None = None

    async def _async_close_api(self) -> None:
        """Close the API client used by the config flow."""
        if (api := self._api) is not None:
            self._api = None
            await api.close()

    @override
    @callback
    def async_remove(self) -> None:
        """Close the API client when the flow is cancelled."""
        if self._api is not None:
            self.hass.async_create_task(self._async_close_api())

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self._async_close_api()
            self._api = VRChatAPI(user_input, user_agent=USER_AGENT)
            try:
                return await self._async_authenticate()
            except TwoFactorAuthRequired as err:
                if err.challenge is TwoFactorAuthChallenge.EMAIL_OTP:
                    return await self.async_step_email_2fa()
                return await self.async_step_2fa()
            except vrchatapi.exceptions.UnauthorizedException:
                await self._async_close_api()
                errors["base"] = "invalid_auth"
            except vrchatapi.exceptions.ApiException, ClientError, TimeoutError:
                await self._async_close_api()
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_USERNAME): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.EMAIL, autocomplete="username"
                        )
                    ),
                    probatio.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.PASSWORD,
                            autocomplete="current-password",
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_email_2fa(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Verify an email two-factor authentication code."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api = self._api
            assert api is not None
            try:
                try:
                    await api.verify2_fa_email_code(user_input[CONF_EMAIL_2FA_CODE])
                except vrchatapi.exceptions.BadRequestException:
                    errors["base"] = "invalid_auth"
                else:
                    return await self._async_authenticate()
            except vrchatapi.exceptions.UnauthorizedException:
                errors["base"] = "invalid_auth"
            except vrchatapi.exceptions.ApiException, ClientError, TimeoutError:
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="email_2fa",
            data_schema=probatio.Schema(
                {probatio.Required(CONF_EMAIL_2FA_CODE): _TWO_FACTOR_CODE}
            ),
            errors=errors,
        )

    async def async_step_2fa(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Verify an authenticator two-factor authentication code."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api = self._api
            assert api is not None
            try:
                try:
                    await api.verify2_fa(user_input[CONF_2FA_CODE])
                except vrchatapi.exceptions.BadRequestException:
                    errors["base"] = "invalid_auth"
                else:
                    return await self._async_authenticate()
            except vrchatapi.exceptions.UnauthorizedException:
                errors["base"] = "invalid_auth"
            except vrchatapi.exceptions.ApiException, ClientError, TimeoutError:
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="2fa",
            data_schema=probatio.Schema(
                {probatio.Required(CONF_2FA_CODE): _TWO_FACTOR_CODE}
            ),
            errors=errors,
        )

    async def _async_authenticate(self) -> ConfigFlowResult:
        """Validate credentials and create a uniquely identified entry."""
        api = self._api
        assert api is not None
        current_user = await api.get_current_user()
        await self.async_set_unique_id(current_user["id"], raise_on_progress=True)
        try:
            self._abort_if_unique_id_configured()
        except AbortFlow:
            await self._async_close_api()
            raise
        await get_vrchat_auth_cookie_store(self.hass, current_user["id"]).async_save(
            api.cookie
        )
        InitialCurrentUserData[current_user["id"]] = current_user
        config = api.config
        await self._async_close_api()
        return self.async_create_entry(
            title=current_user["username"],
            data=config,
        )


_TWO_FACTOR_CODE: Final = TextSelector(
    TextSelectorConfig(type=TextSelectorType.TEL, autocomplete="one-time-code")
)
