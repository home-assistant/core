"""Config flow for the National Grid US integration."""

from collections.abc import Mapping
import logging
from typing import Any

from py_nationalgrid import NationalGridClient, NationalGridConfig, create_cookie_jar
from py_nationalgrid.exceptions import (
    CannotConnectError,
    InvalidAuthError,
    NationalGridError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.util import slugify

from .const import CONF_SELECTED_ACCOUNTS, DOMAIN

_LOGGER = logging.getLogger(__name__)


class NationalGridUSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for National Grid US."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._username: str | None = None
        self._password: str | None = None
        self._accounts: list[dict[str, str]] = []

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
                await self.async_set_unique_id(slugify(self._username))
                self._abort_if_unique_id_configured()

                if len(self._accounts) == 1:
                    return self.async_create_entry(
                        title=self._username or "",
                        data={
                            CONF_USERNAME: self._username,
                            CONF_PASSWORD: self._password,
                            CONF_SELECTED_ACCOUNTS: [
                                self._accounts[0]["billingAccountId"]
                            ],
                        },
                    )
                return await self.async_step_select_accounts()

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

    async def async_step_select_accounts(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the account selection step."""
        if user_input is not None:
            selected = user_input.get(CONF_SELECTED_ACCOUNTS, [])
            if not selected:
                return self.async_show_form(
                    step_id="select_accounts",
                    data_schema=self._get_account_selection_schema(),
                    errors={"base": "no_accounts_selected"},
                )
            return self.async_create_entry(
                title=self._username or "",
                data={
                    CONF_USERNAME: self._username,
                    CONF_PASSWORD: self._password,
                    CONF_SELECTED_ACCOUNTS: selected,
                },
            )

        return self.async_show_form(
            step_id="select_accounts",
            data_schema=self._get_account_selection_schema(),
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        self._username = entry_data.get(CONF_USERNAME)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication confirmation."""
        errors: dict[str, str] = {}
        if user_input is not None:
            username = self._get_reauth_entry().data[CONF_USERNAME]
            try:
                await self._fetch_accounts(username, user_input[CONF_PASSWORD])
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except NationalGridError:
                _LOGGER.exception("Unexpected error during reauth")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data={
                        **self._get_reauth_entry().data,
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        ),
                    ),
                },
            ),
            errors=errors,
            description_placeholders={CONF_USERNAME: self._username or ""},
        )

    def _get_account_selection_schema(self) -> vol.Schema:
        """Get the schema for account selection."""
        return vol.Schema(
            {
                vol.Required(CONF_SELECTED_ACCOUNTS): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value=account["billingAccountId"],
                                label=f"Account {account['billingAccountId']}",
                            )
                            for account in self._accounts
                        ],
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    ),
                ),
            }
        )

    async def _fetch_accounts(
        self, username: str, password: str
    ) -> list[dict[str, str]]:
        """Fetch linked accounts from the API."""
        session = async_create_clientsession(self.hass, cookie_jar=create_cookie_jar())
        client = NationalGridClient(
            config=NationalGridConfig(username=username, password=password),
            session=session,
        )
        async with client:
            accounts = await client.get_linked_accounts()
            return [{"billingAccountId": str(a["billingAccountId"])} for a in accounts]
