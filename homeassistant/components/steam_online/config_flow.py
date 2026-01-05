"""Config flow for Steam integration."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

import steam
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import CONF_ACCOUNT, CONF_ACCOUNTS, DOMAIN, LOGGER, PLACEHOLDERS
from .coordinator import SteamConfigEntry

# To avoid too long request URIs, the amount of ids to request is limited
MAX_IDS_TO_REQUEST = 275


def validate_input(user_input: dict[str, str]) -> dict[str, str | int]:
    """Handle common flow input validation."""
    steam.api.key.set(user_input[CONF_API_KEY])
    interface = steam.api.interface("ISteamUser")
    names = interface.GetPlayerSummaries(steamids=user_input[CONF_ACCOUNT])
    return names["response"]["players"]["player"][0]


class SteamFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Steam."""

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: SteamConfigEntry,
    ) -> SteamOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SteamOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is None and self.source == SOURCE_REAUTH:
            user_input = {CONF_ACCOUNT: self._get_reauth_entry().data[CONF_ACCOUNT]}
        elif user_input is not None:
            try:
                res = await self.hass.async_add_executor_job(validate_input, user_input)
                if res is not None:
                    name = str(res["personaname"])
                else:
                    errors["base"] = "invalid_account"
            except (steam.api.HTTPError, steam.api.HTTPTimeoutError) as ex:
                errors["base"] = "cannot_connect"
                if "403" in str(ex):
                    errors["base"] = "invalid_auth"
            except Exception as ex:  # noqa: BLE001
                LOGGER.exception("Unknown exception: %s", ex)
                errors["base"] = "unknown"
            if not errors:
                entry = await self.async_set_unique_id(user_input[CONF_ACCOUNT])
                if entry and self.source == SOURCE_REAUTH:
                    self.hass.config_entries.async_update_entry(entry, data=user_input)
                    await self.hass.config_entries.async_reload(entry.entry_id)
                    return self.async_abort(reason="reauth_successful")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=name,
                    data=user_input,
                    options={CONF_ACCOUNTS: {user_input[CONF_ACCOUNT]: name}},
                )
        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_API_KEY, default=user_input.get(CONF_API_KEY) or ""
                    ): str,
                    vol.Required(
                        CONF_ACCOUNT, default=user_input.get(CONF_ACCOUNT) or ""
                    ): str,
                }
            ),
            errors=errors,
            description_placeholders=PLACEHOLDERS,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a reauthorization flow request."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is not None:
            return await self.async_step_user()

        self._set_confirm_only()
        return self.async_show_form(
            step_id="reauth_confirm", description_placeholders=PLACEHOLDERS
        )


def _batch_ids(ids: list[str]) -> Iterator[list[str]]:
    for i in range(0, len(ids), MAX_IDS_TO_REQUEST):
        yield ids[i : i + MAX_IDS_TO_REQUEST]


class SteamOptionsFlowHandler(OptionsFlow):
    """Handle Steam client options."""

    def __init__(self, entry: SteamConfigEntry) -> None:
        """Initialize options flow."""
        self.options = dict(entry.options)

    async def async_step_init(
        self, user_input: dict[str, dict[str, str]] | None = None
    ) -> ConfigFlowResult:
        """Manage Steam options."""
        if user_input is not None:
            await self.hass.config_entries.async_unload(self.config_entry.entry_id)
            for _id in self.options[CONF_ACCOUNTS]:
                if _id not in user_input[CONF_ACCOUNTS] and (
                    entity_id := er.async_get(self.hass).async_get_entity_id(
                        Platform.SENSOR, DOMAIN, f"sensor.steam_{_id}"
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
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
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
