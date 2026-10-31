"""Config flow for the Mijn Farmad Apotheek integration."""

from collections.abc import Awaitable, Callable, Mapping
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

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CODE, CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_REFRESH_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)

PASSWORD_SELECTOR = TextSelector(
    TextSelectorConfig(
        type=TextSelectorType.PASSWORD,
        autocomplete="current-password",
    )
)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.EMAIL,
                autocomplete="email",
            )
        ),
        probatio.Required(probatio.Secret(CONF_PASSWORD)): PASSWORD_SELECTOR,
    }
)

STEP_REAUTH_DATA_SCHEMA = probatio.Schema(
    {probatio.Required(probatio.Secret(CONF_PASSWORD)): PASSWORD_SELECTOR}
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
            result, errors = await self._async_attempt_login(user_input)
            if result is not None:
                return result

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

            result, errors = await self._async_attempt_login(
                self._login_data, provide_otp
            )
            if result is not None:
                return result

        return self.async_show_form(
            step_id="mfa",
            data_schema=STEP_MFA_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication after an authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the password to renew the Farmad session."""
        errors: dict[str, str] = {}
        email: str = self._get_reauth_entry().data[CONF_EMAIL]
        if user_input is not None:
            result, errors = await self._async_attempt_login(
                {CONF_EMAIL: email, **user_input}
            )
            if result is not None:
                return result

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            description_placeholders={"account": email},
            errors=errors,
        )

    async def _async_attempt_login(
        self,
        data: dict[str, Any],
        otp_provider: Callable[[], Awaitable[str]] | None = None,
    ) -> tuple[ConfigFlowResult | None, dict[str, str]]:
        """Log in with the credentials and return the next result or form errors.

        Without an otp provider, an account that needs a one-time code moves
        to the code step. With one, every authentication error means the code
        was wrong.
        """
        self._login_data = data
        try:
            account, access_token, refresh_token = await _async_login(
                data, otp_provider
            )
        except FarmadAuthenticationError as err:
            if otp_provider is not None:
                return None, {CONF_CODE: "wrong_code"}
            if isinstance(err, FarmadMfaRequiredError):
                return await self.async_step_mfa(), {}
            return None, {"base": "invalid_auth"}
        except FarmadError:
            return None, {"base": "cannot_connect"}
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return None, {"base": "unknown"}
        return await self._async_finish_login(account, access_token, refresh_token), {}

    async def _async_finish_login(
        self, account: FarmadAccount, access_token: str, refresh_token: str | None
    ) -> ConfigFlowResult:
        """Create the config entry, or renew it during reauthentication."""
        await self.async_set_unique_id(account.id)
        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            data_updates = {CONF_ACCESS_TOKEN: access_token}
            if refresh_token is not None:
                data_updates[CONF_REFRESH_TOKEN] = refresh_token
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data_updates=data_updates
            )
        return self.async_create_entry(
            title=account.full_name,
            data={
                CONF_EMAIL: self._login_data[CONF_EMAIL],
                CONF_ACCESS_TOKEN: access_token,
                CONF_REFRESH_TOKEN: refresh_token,
            },
        )
