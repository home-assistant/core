"""Config flow for the Anglian Water integration."""

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any, override

from aiohttp import CookieJar
from pyanglianwater import AnglianWater
from pyanglianwater.auth import MSOB2CAuth
from pyanglianwater.exceptions import (
    ConsentRequiredError,
    ExpiredAccessTokenError,
    InvalidAccountIdError,
    MFARequiredError,
    SelfAssertedError,
    SmartMeterUnavailableError,
    UnknownEndpointError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CODE,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import CONF_ACCOUNT_NUMBER, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): selector.TextSelector(),
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
)

STEP_MFA_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CODE): selector.TextSelector(),
    }
)


async def validate_credentials(auth: MSOB2CAuth) -> str | None:
    """Validate the provided credentials."""
    try:
        await auth.send_login_request()
    except MFARequiredError:
        return "mfa_required"
    except ConsentRequiredError:
        return "consent_required"
    except SelfAssertedError:
        return "invalid_auth"
    except Exception:
        _LOGGER.exception("Unexpected exception")
        return "unknown"
    return None


def humanize_account_data(account: dict) -> str:
    """Convert an account data into a human-readable format."""
    if account["address"]["company_name"] != "":
        return f"{account['account_number']} - {account['address']['company_name']}"
    if account["address"]["building_name"] != "":
        return f"{account['account_number']} - {account['address']['building_name']}"
    return f"{account['account_number']} - {account['address']['postcode']}"


async def get_accounts(auth: MSOB2CAuth) -> list[selector.SelectOptionDict]:
    """Retrieve the list of accounts associated with the authenticated user."""
    _aw = AnglianWater(authenticator=auth)
    accounts = await _aw.api.get_associated_accounts()
    return [
        selector.SelectOptionDict(
            value=str(account["account_number"]),
            label=humanize_account_data(account),
        )
        for account in accounts["result"]["active"]
    ]


async def validate_account(auth: MSOB2CAuth, account_number: str) -> str | None:
    """Validate the provided account number."""
    _aw = AnglianWater(authenticator=auth)
    try:
        await _aw.validate_smart_meter(account_number)
    except InvalidAccountIdError, SmartMeterUnavailableError:
        return "smart_meter_unavailable"
    return None


class AnglianWaterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Anglian Water."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.authenticator: MSOB2CAuth | None = None
        self.accounts: list[selector.SelectOptionDict] = []
        self.user_input: dict[str, Any] | None = None

    def _create_authenticator(self, user_input: dict[str, Any]) -> MSOB2CAuth:
        """Create an MSOB2CAuth instance with the provided user input."""
        return MSOB2CAuth(
            username=user_input[CONF_USERNAME],
            password=user_input[CONF_PASSWORD],
            session=async_create_clientsession(
                self.hass,
                cookie_jar=CookieJar(quote_cookie=False),
            ),
        )

    async def _async_validate_mfa(self, code: str) -> str | None:
        """Validate the provided MFA code."""
        if TYPE_CHECKING:
            assert self.authenticator
        try:
            await self.authenticator.send_mfa_request(code)
        except MFARequiredError:
            return "invalid_code"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return "unknown"
        return None

    async def _async_get_accounts(self) -> str | None:
        """Retrieve the list of accounts associated with the authenticated user."""
        if TYPE_CHECKING:
            assert self.authenticator
        try:
            self.accounts = await get_accounts(self.authenticator)
        except ExpiredAccessTokenError, UnknownEndpointError:
            _LOGGER.exception("Error retrieving accounts")
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return "unknown"
        return None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.authenticator = self._create_authenticator(user_input)
            validation_error = await validate_credentials(self.authenticator)
            if validation_error == "mfa_required":
                self.user_input = user_input
                return await self.async_step_mfa()
            if validation_error:
                errors["base"] = validation_error
            else:
                account_error = await self._async_get_accounts()
                if not account_error:
                    self.user_input = user_input
                    return await self.async_step_select_account()
                errors["base"] = account_error

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_mfa(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the MFA step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if TYPE_CHECKING:
                assert self.authenticator
            error = await self._async_validate_mfa(user_input[CONF_CODE])
            if error:
                errors["base"] = error
            else:
                account_error = await self._async_get_accounts()
                if not account_error:
                    return await self.async_step_select_account()
                errors["base"] = account_error
        return self.async_show_form(
            step_id="mfa", data_schema=STEP_MFA_DATA_SCHEMA, errors=errors
        )

    async def async_step_select_account(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the account selection step."""
        if len(self.accounts) == 1:
            account_number = self.accounts[0]["value"]
            return await self.async_step_complete(
                {
                    CONF_ACCOUNT_NUMBER: account_number,
                }
            )
        errors: dict[str, str] = {}
        if user_input is not None:
            if TYPE_CHECKING:
                assert self.authenticator
            validation_result = await validate_account(
                self.authenticator,
                user_input[CONF_ACCOUNT_NUMBER],
            )
            if not validation_result:
                return await self.async_step_complete(user_input)
            errors["base"] = validation_result
        return self.async_show_form(
            step_id="select_account",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCOUNT_NUMBER): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=self.accounts,
                            multiple=False,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_complete(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Handle the final configuration step."""
        await self.async_set_unique_id(user_input[CONF_ACCOUNT_NUMBER])
        self._abort_if_unique_id_configured()
        if TYPE_CHECKING:
            assert self.authenticator
            assert self.user_input
        config_entry_data = {
            **self.user_input,
            CONF_ACCOUNT_NUMBER: user_input[CONF_ACCOUNT_NUMBER],
            CONF_ACCESS_TOKEN: self.authenticator.refresh_token,
        }
        return self.async_create_entry(
            title=user_input[CONF_ACCOUNT_NUMBER],
            data=config_entry_data,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Initial configuration step via reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle receiving username/password."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.authenticator = self._create_authenticator(user_input)
            validation_response = await validate_credentials(self.authenticator)
            if not validation_response:
                return await self._async_finish_reauth()
            if validation_response == "mfa_required":
                self.user_input = user_input
                return await self.async_step_reauth_mfa()
            errors["base"] = validation_response
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth_mfa(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the MFA step during reauthentication."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if TYPE_CHECKING:
                assert self.authenticator
            error = await self._async_validate_mfa(user_input[CONF_CODE])
            if not error:
                return await self._async_finish_reauth()
            errors["base"] = error
        return self.async_show_form(
            step_id="reauth_mfa", data_schema=STEP_MFA_DATA_SCHEMA, errors=errors
        )

    async def _async_finish_reauth(self) -> ConfigFlowResult:
        """Verify the account and update its access token."""
        if TYPE_CHECKING:
            assert self.authenticator
        entry = self._get_reauth_entry()
        account_error = await self._async_get_accounts()
        if account_error:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors={"base": account_error},
            )
        if not any(
            account["value"] == entry.data[CONF_ACCOUNT_NUMBER]
            for account in self.accounts
        ):
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors={"base": "account_not_found"},
            )
        return self.async_update_reload_and_abort(
            entry,
            data_updates={CONF_ACCESS_TOKEN: self.authenticator.refresh_token},
        )
