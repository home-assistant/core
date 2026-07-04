"""Config flow for Steam integration."""

from collections.abc import Iterator, Mapping
import logging
from typing import Any, override

import steam.api
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME, Platform
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import CONF_ACCOUNT, CONF_ACCOUNTS, DOMAIN, PLACEHOLDERS
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

    VERSION = 2

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: SteamConfigEntry,
    ) -> SteamOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SteamOptionsFlowHandler(config_entry)

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_ACCOUNT])
            self._abort_if_unique_id_configured()
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
                return self.async_create_entry(
                    title=name,
                    data=user_input,
                    options={CONF_ACCOUNTS: {user_input[CONF_ACCOUNT]: name}},
                )
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


def _batch_ids(ids: list[str]) -> Iterator[list[str]]:
    for i in range(0, len(ids), MAX_IDS_TO_REQUEST):
        yield ids[i : i + MAX_IDS_TO_REQUEST]


class SteamOptionsFlowHandler(OptionsFlowWithReload):
    """Handle Steam client options."""

    def __init__(self, entry: SteamConfigEntry) -> None:
        """Initialize options flow."""
        self.options = dict(entry.options)

    async def async_step_init(
        self, user_input: dict[str, dict[str, str]] | None = None
    ) -> ConfigFlowResult:
        """Manage Steam options."""
        if user_input is not None:
            for _id in self.options[CONF_ACCOUNTS]:
                if _id not in user_input[CONF_ACCOUNTS] and (
                    entity_id := er.async_get(self.hass).async_get_entity_id(
                        Platform.SENSOR, DOMAIN, f"{_id}_account"
                    )
                ):
                    er.async_get(self.hass).async_remove(entity_id)
            channel_data = {
                CONF_ACCOUNTS: {
                    _id: name
                    for _id, name in self.options[CONF_ACCOUNTS].items()
                    if _id in user_input[CONF_ACCOUNTS]
                }
            }
            return self.async_create_entry(title="", data=channel_data)
        error = None
        try:
            users = {
                name["steamid"]: name["personaname"]
                for name in await self.hass.async_add_executor_job(self.get_accounts)
            }
            if not users:
                error = {"base": "unauthorized"}

        except steam.api.HTTPTimeoutError:
            users = self.options[CONF_ACCOUNTS]

        options = {
            vol.Required(
                CONF_ACCOUNTS,
                default=set(self.options[CONF_ACCOUNTS]),
            ): cv.multi_select(users | self.options[CONF_ACCOUNTS]),
        }
        self.options[CONF_ACCOUNTS] = users | self.options[CONF_ACCOUNTS]

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(options), errors=error
        )

    def get_accounts(self) -> list[dict[str, str | int]]:
        """Get accounts."""
        interface = steam.api.interface("ISteamUser")
        try:
            friends = interface.GetFriendList(
                steamid=self.config_entry.data[CONF_ACCOUNT]
            )
            _users_str = [user["steamid"] for user in friends["friendslist"]["friends"]]
        except steam.api.HTTPError:
            return []
        names = []
        for id_batch in _batch_ids(_users_str):
            names.extend(
                interface.GetPlayerSummaries(steamids=id_batch)["response"]["players"][
                    "player"
                ]
            )
        return names
