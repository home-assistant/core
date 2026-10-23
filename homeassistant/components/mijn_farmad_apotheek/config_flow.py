"""Config flow for the Mijn Farmad Apotheek integration."""

from collections.abc import Awaitable, Callable
import logging
from typing import Any, override

from aiofarmad import (
    FarmadAccount,
    FarmadAuthenticationError,
    FarmadClient,
    FarmadError,
    FarmadMfaRequiredError,
)
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CODE, CONF_EMAIL, CONF_PASSWORD

from .const import CONF_REFRESH_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_EMAIL): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
    }
)

STEP_MFA_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_CODE): probatio.All(
            probatio.Coerce(str), probatio.Match(r"^[0-9]{6}\Z")
        )
    }
)


async def _async_login(
    data: dict[str, Any],
    otp_provider: Callable[[], Awaitable[str]] | None = None,
) -> tuple[FarmadAccount, str, str | None]:
    """Log in with the given credentials and return the account and token pair.

    The otp provider answers the code challenge of accounts with
    multi-factor authentication and is ignored by accounts without one.
    """
    client = FarmadClient(
        email=data[CONF_EMAIL],
        password=data[CONF_PASSWORD],
        otp_provider=otp_provider,
    )
    try:
        await client.async_login()
        account = await client.async_get_account()
        if (access_token := client.access_token) is None:
            raise FarmadAuthenticationError("Login returned no access token")
        return account, access_token, client.refresh_token
    finally:
        await client.async_close()


class FarmadConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Mijn Farmad Apotheek config flow."""

    VERSION = 1

    _login_data: dict[str, Any]

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                account, access_token, refresh_token = await _async_login(user_input)
            except FarmadMfaRequiredError:
                self._login_data = user_input
                return await self.async_step_mfa()
            except FarmadAuthenticationError:
                errors["base"] = "invalid_auth"
            except FarmadError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return await self._async_finish_login(
                    account, access_token, refresh_token
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_mfa(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the one-time code step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            otp: str = user_input[CONF_CODE]

            async def provide_otp() -> str:
                """Return the one-time code the user typed."""
                return otp

            try:
                account, access_token, refresh_token = await _async_login(
                    self._login_data, provide_otp
                )
            except FarmadAuthenticationError:
                errors[CONF_CODE] = "wrong_code"
            except FarmadError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return await self._async_finish_login(
                    account, access_token, refresh_token
                )

        return self.async_show_form(
            step_id="mfa",
            data_schema=STEP_MFA_DATA_SCHEMA,
            errors=errors,
        )

    async def _async_finish_login(
        self, account: FarmadAccount, access_token: str, refresh_token: str | None
    ) -> ConfigFlowResult:
        """Create the config entry for the logged in account."""
        await self.async_set_unique_id(account.id)
        return self.async_create_entry(
            title=account.full_name,
            data={
                CONF_ACCESS_TOKEN: access_token,
                CONF_REFRESH_TOKEN: refresh_token,
            },
        )
