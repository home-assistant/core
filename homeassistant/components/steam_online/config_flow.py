"""Config flow for Steam integration."""

from collections.abc import Mapping
from itertools import batched
import logging
from typing import TYPE_CHECKING, Any, override

import steam.api
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import CONF_ACCOUNT, DOMAIN, PLACEHOLDERS, SUBENTRY_TYPE_FRIEND
from .coordinator import SteamConfigEntry

_LOGGER = logging.getLogger(__name__)


# To avoid too long request URIs, the amount of ids to request is limited
MAX_IDS_TO_REQUEST = 275

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_ACCOUNT): str,
    }
)
STEP_REAUTH_DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})


def validate_input(user_input: dict[str, str]) -> dict[str, str | int]:
    """Handle common flow input validation."""
    steam.api.key.set(user_input[CONF_API_KEY])
    interface = steam.api.interface("ISteamUser")
    names = interface.GetPlayerSummaries(steamids=user_input[CONF_ACCOUNT])
    return names["response"]["players"]["player"][0]


class SteamFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Steam."""

    VERSION = 3

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: SteamConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {SUBENTRY_TYPE_FRIEND: FriendSubentryFlowHandler}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_ACCOUNT])
            self._abort_if_unique_id_configured()

            config_entries = self.hass.config_entries.async_entries(DOMAIN)
            for entry in config_entries:
                if user_input[CONF_ACCOUNT] in {
                    subentry.unique_id for subentry in entry.subentries.values()
                }:
                    return self.async_abort(reason="already_configured_as_subentry")

            try:
                res = await self.hass.async_add_executor_job(validate_input, user_input)
                if res is not None:
                    name = str(res["personaname"])
                else:
                    errors["base"] = "invalid_account"
            except steam.api.HTTPTimeoutError:
                errors["base"] = "timeout_connect"
            except steam.api.HTTPError as ex:
                errors["base"] = (
                    "invalid_auth" if "403" in str(ex) else "cannot_connect"
                )
            except Exception:
                _LOGGER.exception("Unknown exception")
                errors["base"] = "unknown"
            if not errors:
                return self.async_create_entry(title=name, data=user_input)
        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_DATA_SCHEMA, suggested_values=user_input
            ),
            errors=errors,
            description_placeholders=PLACEHOLDERS,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a reauthorization flow request."""
        return await self.async_step_reauth_confirm()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfigure flow."""
        return await self.async_step_reauth_confirm(user_input)

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        errors: dict[str, str] = {}
        entry = (
            self._get_reauth_entry()
            if self.source == SOURCE_REAUTH
            else self._get_reconfigure_entry()
        )

        if user_input is not None:
            try:
                if not await self.hass.async_add_executor_job(
                    validate_input, {**entry.data, **user_input}
                ):
                    errors["base"] = "invalid_account"
            except steam.api.HTTPTimeoutError:
                errors["base"] = "timeout_connect"
            except steam.api.HTTPError as ex:
                errors["base"] = (
                    "invalid_auth" if "403" in str(ex) else "cannot_connect"
                )
            except Exception:
                _LOGGER.exception("Unknown exception")
                errors["base"] = "unknown"

            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input
                )
        return self.async_show_form(
            step_id=(
                "reauth_confirm" if self.source == SOURCE_REAUTH else SOURCE_RECONFIGURE
            ),
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_REAUTH_DATA_SCHEMA, suggested_values=user_input
            ),
            errors=errors,
            description_placeholders={CONF_NAME: entry.title, **PLACEHOLDERS},
        )


class FriendSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding a friend."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Subentry user flow."""
        errors: dict[str, str] = {}
        config_entry: SteamConfigEntry = self._get_entry()

        if config_entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="config_entry_not_loaded")

        client = config_entry.runtime_data.user_interface
        if TYPE_CHECKING:
            assert config_entry.unique_id

        if user_input is not None:
            config_entries = self.hass.config_entries.async_entries(DOMAIN)
            if user_input[CONF_ACCOUNT] in {
                entry.unique_id for entry in config_entries
            }:
                return self.async_abort(reason="already_configured_as_entry")
            for entry in config_entries:
                if user_input[CONF_ACCOUNT] in {
                    subentry.unique_id
                    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_FRIEND)
                }:
                    return self.async_abort(reason="already_configured")

            try:
                title = await self.hass.async_add_executor_job(
                    lambda: client.GetPlayerSummaries(
                        steamids=[user_input[CONF_ACCOUNT]]
                    )["response"]["players"]["player"][0]["personaname"]
                )
            except steam.api.HTTPTimeoutError:
                errors["base"] = "timeout_connect"
            except steam.api.HTTPError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unknown exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=title,
                    data={},
                    unique_id=user_input[CONF_ACCOUNT],
                )

        def get_accounts() -> list[dict[str, Any]]:
            friends = client.GetFriendList(steamid=config_entry.unique_id)[
                "friendslist"
            ]["friends"]
            accounts = []
            for steamids in batched(
                [friend["steamid"] for friend in friends],
                MAX_IDS_TO_REQUEST,
                strict=False,
            ):
                accounts.extend(
                    client.GetPlayerSummaries(steamids=list(steamids))["response"][
                        "players"
                    ]["player"]
                )
            return accounts

        try:
            accounts = await self.hass.async_add_executor_job(get_accounts)
        except steam.api.HTTPTimeoutError:
            return self.async_abort(reason="timeout_connect")
        except steam.api.HTTPError as e:
            if "401" in str(e):
                return self.async_abort(reason="friendlist_private")
            return self.async_abort(reason="cannot_connect")

        existing_subentries = {
            subentry.unique_id
            for subentry in config_entry.get_subentries_of_type(SUBENTRY_TYPE_FRIEND)
        }
        options = [
            SelectOptionDict(
                value=account["steamid"],
                label=account["personaname"],
            )
            for account in accounts
            if account["steamid"] not in existing_subentries
        ]

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_ACCOUNT): SelectSelector(
                            SelectSelectorConfig(options=options, sort=True)
                        )
                    }
                ),
                user_input,
            ),
            errors=errors,
        )
