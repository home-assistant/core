"""Config flow for the National Grid US integration."""

import logging
from typing import Any, override

from py_nationalgrid import NationalGridClient, NationalGridConfig, create_cookie_jar
from py_nationalgrid.exceptions import (
    CannotConnectError,
    InvalidAuthError,
    NationalGridError,
    RetryExhaustedError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import CONF_ACCOUNT_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


class NationalGridUSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for National Grid US."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._username: str | None = None
        self._password: str | None = None
        self._accounts: list[dict[str, str]] = []

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial credentials step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]

            try:
                self._accounts = await self._fetch_accounts(
                    self._username, self._password
                )
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except NationalGridError:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"
            else:
                if not self._accounts:
                    _LOGGER.error("Login succeeded but no accounts returned")
                    return self.async_abort(reason="no_accounts_found")

                # Drop accounts that already have a config entry so each
                # billing account maps to exactly one entry.
                configured = self._async_current_ids()
                available = [
                    account
                    for account in self._accounts
                    if account["billingAccountId"] not in configured
                ]
                if not available:
                    return self.async_abort(reason="already_configured")

                self._accounts = available
                if len(self._accounts) == 1:
                    return await self._async_create_account_entry(
                        self._accounts[0]["billingAccountId"]
                    )
                return await self.async_step_select_account()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=(user_input or {}).get(CONF_USERNAME, vol.UNDEFINED),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        ),
                    ),
                },
            ),
            errors=errors,
        )

    async def async_step_select_account(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the account selection step."""
        if user_input is not None:
            return await self._async_create_account_entry(user_input[CONF_ACCOUNT_ID])

        return self.async_show_form(
            step_id="select_account",
            data_schema=self._get_account_selection_schema(),
        )

    async def _async_create_account_entry(self, account_id: str) -> ConfigFlowResult:
        """Create a config entry for a single billing account."""
        await self.async_set_unique_id(account_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=self._account_title(account_id),
            data={
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_ACCOUNT_ID: account_id,
            },
        )

    def _account_title(self, account_id: str) -> str:
        """Build a human-readable title for an account entry."""
        for account in self._accounts:
            if account["billingAccountId"] == account_id:
                if address := account.get("service_address"):
                    return f"{account_id} ({address})"
                break
        return account_id

    def _get_account_selection_schema(self) -> vol.Schema:
        """Get the schema for account selection."""
        options: list[selector.SelectOptionDict] = []
        for account in self._accounts:
            label = f"Account {account['billingAccountId']}"
            if address := account.get("service_address"):
                label = f"{label} — {address}"
            options.append(
                selector.SelectOptionDict(
                    value=account["billingAccountId"],
                    label=label,
                )
            )
        return vol.Schema(
            {
                vol.Required(CONF_ACCOUNT_ID): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        mode=selector.SelectSelectorMode.LIST,
                    ),
                ),
            }
        )

    async def _fetch_accounts(
        self, username: str, password: str
    ) -> list[dict[str, str]]:
        """Fetch linked accounts, enriched with their service address."""
        session = async_create_clientsession(self.hass, cookie_jar=create_cookie_jar())
        client = NationalGridClient(
            config=NationalGridConfig(username=username, password=password),
            session=session,
        )
        async with client:
            accounts = await client.get_linked_accounts()
            result: list[dict[str, str]] = []
            for account in accounts:
                account_id = str(account["billingAccountId"])
                entry = {"billingAccountId": account_id}
                # The service address is only used to label the account in the
                # selection step, so a failed lookup degrades to the bare ID.
                try:
                    billing = await client.get_billing_account(account_id)
                except (
                    CannotConnectError,
                    RetryExhaustedError,
                    NationalGridError,
                ) as err:
                    _LOGGER.debug(
                        "Could not fetch service address for account %s: %s",
                        account_id,
                        err,
                    )
                else:
                    if address := billing.get("serviceAddress", {}).get(
                        "serviceAddressCompressed"
                    ):
                        entry["service_address"] = address
                result.append(entry)
            return result
