"""Config flow for Steam integration."""
from __future__ import annotations

import functools as ft
from typing import Any

import steam
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import CONF_ACCOUNT, CONF_ACCOUNTS, DEFAULT_NAME, DOMAIN, LOGGER


async def validate_input(user_input: dict, hass: HomeAssistant) -> list[dict[str, str]]:
    """Handle common flow input validation."""
    steam.api.key.set(user_input[CONF_API_KEY])
    interface = await hass.async_add_executor_job(steam.api.interface, "ISteamUser")
    names = await hass.async_add_executor_job(
        ft.partial(interface.GetPlayerSummaries, steamids=user_input[CONF_ACCOUNT])
    )
    return (await hass.async_add_executor_job(names.get, "response"))["players"][
        "player"
    ]


class SteamFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for team."""

    def __init__(self) -> None:
        """Initialize the flow."""
        self.entry: config_entries.ConfigEntry | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return SteamOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is None and self.entry:
            user_input = {CONF_ACCOUNT: self.entry.data[CONF_ACCOUNT]}
        elif user_input is not None:
            try:
                res = await validate_input(user_input, self.hass)
                if res[0] is not None:
                    name = res[0]["personaname"]
                else:
                    errors = {"base": "invalid_account"}
            except (steam.api.HTTPError, steam.api.HTTPTimeoutError) as ex:
                errors = {"base": "cannot_connect"}
                if "403" in str(ex):
                    errors = {"base": "invalid_auth"}
            except Exception:  # pylint:disable=broad-except
                errors = {"base": "unknown"}
            if not errors:
                entry = await self.async_set_unique_id(user_input[CONF_ACCOUNT])
                if entry and self.source == config_entries.SOURCE_REAUTH:
                    self.hass.config_entries.async_update_entry(entry, data=user_input)
                    await self.hass.config_entries.async_reload(entry.entry_id)
                    return self.async_abort(reason="reauth_successful")
                self._abort_if_unique_id_configured()
                if self.source == config_entries.SOURCE_IMPORT:
                    accounts_data = {
                        CONF_ACCOUNTS: {
                            acc["steamid"]: {
                                "name": acc["personaname"],
                                "enabled": True,
                            }
                            for acc in res
                        }
                    }
                    user_input.pop(CONF_ACCOUNTS)
                else:
                    accounts_data = {
                        CONF_ACCOUNTS: {
                            user_input[CONF_ACCOUNT]: {"name": name, "enabled": True}
                        }
                    }
                return self.async_create_entry(
                    title=name or DEFAULT_NAME,
                    data=user_input,
                    options=accounts_data,
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
        )

    async def async_step_import(self, import_config: ConfigType) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        for entry in self._async_current_entries():
            if entry.data[CONF_API_KEY] == import_config[CONF_API_KEY]:
                return self.async_abort(reason="already_configured")
        _msg = "Steam yaml config in now deprecated and has been imported. Please remove it from your config"
        LOGGER.warning(_msg)
        import_config[CONF_ACCOUNT] = import_config[CONF_ACCOUNTS][0]
        return await self.async_step_user(import_config)

    async def async_step_reauth(self, user_input: dict[str, str]) -> FlowResult:
        """Handle a reauthorization flow request."""
        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        if user_input is not None:
            return await self.async_step_user()

        self._set_confirm_only()
        return self.async_show_form(step_id="reauth_confirm")


class SteamOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Steam client options."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.entry = entry
        self.options = dict(entry.options)

    async def async_step_init(
        self, user_input: dict[str, dict[str, str]] | None = None
    ) -> FlowResult:
        """Manage Steam options."""
        if user_input is None:
            try:
                interface = await self.hass.async_add_executor_job(
                    steam.api.interface, "ISteamUser"
                )
                friends = await self.hass.async_add_executor_job(
                    ft.partial(
                        interface.GetFriendList, steamid=self.entry.data[CONF_ACCOUNT]
                    )
                )
                friends = (
                    await self.hass.async_add_executor_job(friends.get, "friendslist")
                )["friends"]
                _users_str = str([user["steamid"] for user in friends])
                names = await self.hass.async_add_executor_job(
                    ft.partial(interface.GetPlayerSummaries, steamids=_users_str)
                )
                names = (await self.hass.async_add_executor_job(names.get, "response"))[
                    "players"
                ]["player"]
                users = {
                    name["steamid"]: {"name": name["personaname"], "enabled": False}
                    for name in names
                }
            except steam.api.HTTPTimeoutError:
                users = self.options[CONF_ACCOUNTS]
            _users = users | self.options[CONF_ACCOUNTS]
            self.options[CONF_ACCOUNTS] = {
                k: v
                for k, v in _users.items()
                if k in users.keys() or self.options[CONF_ACCOUNTS][k]["enabled"]
            }

        else:
            await self.hass.config_entries.async_unload(self.entry.entry_id)
            for k in self.options[CONF_ACCOUNTS].keys():
                if (
                    self.options[CONF_ACCOUNTS][k]["enabled"]
                    and k not in user_input[CONF_ACCOUNTS]
                    and (
                        entity_id := er.async_get(self.hass).async_get_entity_id(
                            Platform.SENSOR, DOMAIN, f"sensor.steam_{k}"
                        )
                    )
                ):
                    er.async_get(self.hass).async_remove(entity_id)
            channel_data = {
                CONF_ACCOUNTS: {
                    k: {
                        "name": v["name"],
                        "enabled": bool(k in user_input[CONF_ACCOUNTS]),
                    }
                    for k, v in self.options[CONF_ACCOUNTS].items()
                    if k in user_input[CONF_ACCOUNTS]
                }
            }
            await self.hass.config_entries.async_reload(self.entry.entry_id)
            return self.async_create_entry(title="", data=channel_data)
        options = {
            vol.Required(
                CONF_ACCOUNTS,
                default={
                    k
                    for k in self.options[CONF_ACCOUNTS].keys()
                    if self.options[CONF_ACCOUNTS][k]["enabled"]
                },
            ): cv.multi_select(
                {k: v["name"] for k, v in self.options[CONF_ACCOUNTS].items()}
            ),
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))
