"""Config Flow for Flick Electric integration."""

import asyncio
import logging
from typing import Any

from pyflick import FlickAPI
from pyflick.authentication import AbstractFlickAuth, AuthException, SimpleFlickAuth
from pyflick.const import DEFAULT_CLIENT_ID, DEFAULT_CLIENT_SECRET
from pyflick.types import CustomerAccount
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_ACCOUNT_ID, CONF_SUPPLY_NODE_REF, DOMAIN

_LOGGER = logging.getLogger(__name__)

LOGIN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_CLIENT_ID): str,
        vol.Optional(CONF_CLIENT_SECRET): str,
    }
)


class FlickConfigFlow(ConfigFlow, domain=DOMAIN):
    """Flick config flow."""

    VERSION = 2
    auth: AbstractFlickAuth
    accounts: list[CustomerAccount]
    data: dict[str, Any]

    async def _validate_input(self, user_input: dict[str, Any]) -> bool:
        self.auth = SimpleFlickAuth(
            # TODO: Remove UAT
            host="https://api.flickuat.com",
            username=user_input[CONF_USERNAME],
            password=user_input[CONF_PASSWORD],
            websession=aiohttp_client.async_get_clientsession(self.hass),
            client_id=user_input.get(CONF_CLIENT_ID, DEFAULT_CLIENT_ID),
            client_secret=user_input.get(CONF_CLIENT_SECRET, DEFAULT_CLIENT_SECRET),
        )

        try:
            async with asyncio.timeout(60):
                token = await self.auth.async_get_access_token()
        except TimeoutError as err:
            raise CannotConnect from err
        except AuthException as err:
            raise InvalidAuth from err

        return token is not None

    async def async_step_select_account(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask user to select account."""

        errors = {}
        if user_input is not None:
            self.data[CONF_SUPPLY_NODE_REF] = self._get_supply_node_ref(
                user_input[CONF_ACCOUNT_ID]
            )

            if self.data[CONF_SUPPLY_NODE_REF] is None:
                errors["base"] = "not_active"
            else:
                try:
                    # Ensure supply node is still active
                    await FlickAPI(self.auth).getPricing(
                        self.data[CONF_SUPPLY_NODE_REF]
                    )

                    return await self._async_create_entry()
                except:  # noqa: E722
                    errors["base"] = "cannot_connect"

        self.accounts = await FlickAPI(self.auth).getCustomerAccounts()

        active_accounts = [a for a in self.accounts if a["status"] == "active"]

        if len(active_accounts) == 0:
            return self.async_abort(reason="no_accounts")

        if len(active_accounts) == 1:
            self.data[CONF_SUPPLY_NODE_REF] = self._get_supply_node_ref(
                active_accounts[0]["id"]
            )

            if self.data[CONF_SUPPLY_NODE_REF] is not None:
                return await self._async_create_entry()

        return self.async_show_form(
            step_id="select_account",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCOUNT_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=account["id"], label=account_name(account)
                                )
                                for account in self.accounts
                            ],
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle gathering login info."""
        errors = {}
        if user_input is not None:
            try:
                await self._validate_input(user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self.data = user_input
                return await self.async_step_select_account()

        return self.async_show_form(
            step_id="user", data_schema=LOGIN_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Handle re-authentication."""

        self.data = {**user_input}

        if await self._validate_input(self.data):
            await self.async_step_select_account(self.data)

        if user_input is None:
            return await self.async_step_user()

        return await self.async_step_user(user_input)

    async def _async_create_entry(self) -> ConfigFlowResult:
        """Create an entry for the flow."""

        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch()

            # Migration completed
            if self._get_reauth_entry().version == 1:
                self.hass.config_entries.async_update_entry(
                    self._get_reauth_entry(), data=self.data, version=2
                )

            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=self.data
            )

        # TODO: Use account ID
        await self.async_set_unique_id(f"flick_electric_{self.data[CONF_USERNAME]}")
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"Flick Electric: {self.data[CONF_USERNAME]}",
            data=self.data,
        )

    def _get_supply_node_ref(self, account_id: str) -> str | None:
        """Get the supply node ref for the account."""
        account = next(a for a in self.accounts if a["id"] == account_id)

        main_consumer = account["main_consumer"]

        if main_consumer is None:
            return None

        return main_consumer[CONF_SUPPLY_NODE_REF]


def account_name(account: CustomerAccount) -> str:
    """Generate a name for the account."""
    name = account["address"]
    if account["status"] != "active":
        name += f" [{account['status']}]"

    return name


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
