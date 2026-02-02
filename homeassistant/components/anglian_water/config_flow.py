"""Config flow for the Anglian Water integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from aiohttp import CookieJar
from pyanglianwater import AnglianWater
from pyanglianwater.auth import MSOB2CAuth
from pyanglianwater.exceptions import (
    InvalidAccountIdError,
    SelfAssertedError,
    SmartMeterUnavailableError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_PASSWORD, CONF_USERNAME
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


async def validate_credentials(auth: MSOB2CAuth) -> str | MSOB2CAuth:
    """Validate the provided credentials."""
    try:
        await auth.send_login_request()
    except SelfAssertedError:
        return "invalid_auth"
    except Exception:
        _LOGGER.exception("Unexpected exception")
        return "unknown"
    return auth


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


async def validate_account(auth: MSOB2CAuth, account_number: str) -> str | MSOB2CAuth:
    """Validate the provided account number."""
    _aw = AnglianWater(authenticator=auth)
    try:
        await _aw.validate_smart_meter(account_number)
    except (InvalidAccountIdError, SmartMeterUnavailableError):
        return "smart_meter_unavailable"
    return auth


class AnglianWaterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Anglian Water."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.authenticator: MSOB2CAuth | None = None
        self.accounts: list[selector.SelectOptionDict] = []
        self.user_input: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.authenticator = MSOB2CAuth(
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                session=async_create_clientsession(
                    self.hass,
                    cookie_jar=CookieJar(quote_cookie=False),
                ),
            )
            validation_response = await validate_credentials(self.authenticator)
            if isinstance(validation_response, str):
                errors["base"] = validation_response
            else:
                self.accounts = await get_accounts(self.authenticator)
                if len(self.accounts) > 1:
                    self.user_input = user_input
                    return await self.async_step_select_account()
                account_number = self.accounts[0]["value"]
                self.user_input = user_input
                return await self.async_step_complete(
                    {
                        CONF_ACCOUNT_NUMBER: account_number,
                    }
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_select_account(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the account selection step."""
        errors = {}
        if user_input is not None:
            if TYPE_CHECKING:
                assert self.authenticator
            validation_result = await validate_account(
                self.authenticator,
                user_input[CONF_ACCOUNT_NUMBER],
            )
            if isinstance(validation_result, str):
                errors["base"] = validation_result
            else:
                return await self.async_step_complete(user_input)
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
