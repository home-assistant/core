"""Config flow for Sequence integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    SequenceApiClient,
    SequenceApiError,
    SequenceAuthError,
    SequenceConnectionError,
)
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_INVESTMENT_ACCOUNTS,
    CONF_LIABILITY_ACCOUNTS,
    CONF_LIABILITY_CONFIGURED,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_TOKEN): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    session = async_get_clientsession(hass)
    client = SequenceApiClient(session, data[CONF_ACCESS_TOKEN])

    # Test the connection and get account info for unique ID
    accounts_data = await client.async_get_accounts()

    # We'll use the first pod account ID as unique identifier, or fallback to a hash of token
    pod_accounts = client.get_pod_accounts(accounts_data)
    if pod_accounts:
        unique_id = str(pod_accounts[0]["id"])
        title = f"Sequence ({len(pod_accounts)} pods)"
    else:
        # Fallback if no pods exist yet
        unique_id = data[CONF_ACCESS_TOKEN][-8:]  # Last 8 chars of token
        title = "Sequence"

    return {"title": title, "unique_id": unique_id}


class SequenceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sequence."""

    VERSION = 1
    MINOR_VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SequenceOptionsFlow:
        """Get the options flow for this handler."""
        return SequenceOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except SequenceAuthError:
                errors["base"] = "invalid_auth"
            except SequenceConnectionError:
                errors["base"] = "cannot_connect"
            except SequenceApiError:
                errors["base"] = "unknown"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["unique_id"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth flow."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirm step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except SequenceAuthError:
                errors["base"] = "invalid_auth"
            except SequenceConnectionError:
                errors["base"] = "cannot_connect"
            except SequenceApiError:
                errors["base"] = "unknown"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                reauth_entry = self._get_reauth_entry()
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"account": self._get_reauth_entry().title},
        )


class SequenceOptionsFlow(OptionsFlow):
    """Handle options flow for Sequence integration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Filter out 'none' selections and mark liability configuration as completed
            filtered_input: dict[str, Any] = {}
            for key, value in user_input.items():
                if isinstance(value, list):
                    # Remove 'none' from lists
                    filtered_value = [v for v in value if v != "none"]
                    filtered_input[key] = filtered_value
                else:
                    filtered_input[key] = value

            # Mark liability configuration as completed
            filtered_input[CONF_LIABILITY_CONFIGURED] = True
            return self.async_create_entry(title="", data=filtered_input)

        # Get current account information to show available accounts
        session = async_get_clientsession(self.hass)
        client = SequenceApiClient(session, self.config_entry.data[CONF_ACCESS_TOKEN])

        try:
            accounts_data = await client.async_get_accounts()
            # Get all "Account" type accounts (external accounts)
            all_accounts = accounts_data.get("data", {}).get("accounts", [])
            external_accounts = [
                acc for acc in all_accounts if acc.get("type") == "Account"
            ]

            # Create choices for multi-select
            account_choices = {
                str(acc["id"]): f"{acc['name']} (ID: {acc['id']})"
                for acc in external_accounts
            }

        except Exception:
            _LOGGER.exception("Error fetching accounts for options")
            errors["base"] = "cannot_connect"
            account_choices = {}

        # Current settings
        current_liability_accounts = self.config_entry.options.get(
            CONF_LIABILITY_ACCOUNTS, []
        )
        current_investment_accounts = self.config_entry.options.get(
            CONF_INVESTMENT_ACCOUNTS, []
        )

        # Add 'None' option to account choices
        account_choices_with_none = {
            "none": "None - No liabilities/investments",
            **account_choices,
        }

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_LIABILITY_ACCOUNTS,
                    default=current_liability_accounts,
                ): cv.multi_select(account_choices_with_none),
                vol.Optional(
                    CONF_INVESTMENT_ACCOUNTS,
                    default=current_investment_accounts,
                ): cv.multi_select(account_choices_with_none),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            errors=errors,
            description_placeholders={
                "account_count": str(len(account_choices)),
            },
        )
