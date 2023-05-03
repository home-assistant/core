"""Config flow for LastFm."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pylast import LastFMNetwork, User, WSError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)
from homeassistant.helpers.typing import ConfigType

from .const import CONF_MAIN_USER, CONF_USERS, DOMAIN, LOGGER

PLACEHOLDERS = {"api_account_url": "https://www.last.fm/api/account/create"}

INITIAL_CONFIG_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_MAIN_USER): str,
    }
)


class LastFmFlowHandler:
    """Base handler for LastFM flows."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Initialize LastFM flow."""
        self.data = data

    def _get_lastfm_user(self, username: str) -> User:
        return LastFMNetwork(api_key=self.data[CONF_API_KEY]).get_user(username)

    def _validate_lastfm_user(self, user: User) -> dict[str, str] | None:
        errors = {}
        try:
            user.get_playcount()
        except WSError as error:
            LOGGER.error(error)
            if error.details == "User not found":
                errors["base"] = "invalid_account"
            elif (
                error.details
                == "Invalid API key - You must be granted a valid key by last.fm"
            ):
                errors["base"] = "invalid_auth"
            else:
                errors["base"] = "unknown"
        except Exception:  # pylint:disable=broad-except
            errors["base"] = "unknown"
        if not errors:
            return None
        return errors


class LastFmConfigFlowHandler(ConfigFlow, LastFmFlowHandler, domain=DOMAIN):
    """Config flow handler for LastFm."""

    def __init__(self) -> None:
        """Initialize config flow."""
        super().__init__({})

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Get the options flow for this handler."""
        return LastFmOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Initialize user input."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.data[CONF_API_KEY] = user_input[CONF_API_KEY]
            self.data[CONF_MAIN_USER] = user_input[CONF_MAIN_USER]
            main_user = self._get_lastfm_user(self.data[CONF_MAIN_USER])
            lastfm_errors = self._validate_lastfm_user(main_user)
            if not lastfm_errors:
                return await self.async_step_friends()
            errors = lastfm_errors
        return self.async_show_form(
            step_id="user",
            errors=errors,
            description_placeholders=PLACEHOLDERS,
            data_schema=self.add_suggested_values_to_schema(
                INITIAL_CONFIG_SCHEMA, user_input
            ),
        )

    async def async_step_friends(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Form to select other users and friends."""
        errors = {}
        valid_users = []
        if user_input is not None:
            for user in user_input[CONF_USERS]:
                lastfm_user = self._get_lastfm_user(user)
                lastfm_errors = self._validate_lastfm_user(lastfm_user)
                if lastfm_errors:
                    errors = lastfm_errors
                else:
                    valid_users.append(user)
            if not errors:
                return self.async_create_entry(
                    title="LastFM",
                    data={
                        CONF_API_KEY: self.data[CONF_API_KEY],
                        CONF_MAIN_USER: self.data[CONF_MAIN_USER],
                        CONF_USERS: [
                            self.data[CONF_MAIN_USER],
                            *user_input[CONF_USERS],
                        ],
                    },
                )
        try:
            main_user = self._get_lastfm_user(self.data[CONF_MAIN_USER])
            friends: Sequence[SelectOptionDict] = [
                {"value": str(friend.name), "label": str(friend.get_name(True))}
                for friend in main_user.get_friends()
            ]
        except WSError:
            friends = []
        return self.async_show_form(
            step_id="friends",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERS, default=valid_users): SelectSelector(
                        SelectSelectorConfig(
                            options=friends, custom_value=True, multiple=True
                        )
                    ),
                }
            ),
        )

    async def async_step_import(self, import_config: ConfigType) -> FlowResult:
        """Import config from yaml."""
        for entry in self._async_current_entries():
            if entry.data[CONF_API_KEY] == import_config[CONF_API_KEY]:
                return self.async_abort(reason="already_configured")
        return self.async_create_entry(
            title="LastFM",
            data={
                CONF_API_KEY: import_config[CONF_API_KEY],
                CONF_MAIN_USER: None,
                CONF_USERS: import_config[CONF_USERS],
            },
        )


class LastFmOptionsFlowHandler(OptionsFlow, LastFmFlowHandler):
    """LastFm Options flow handler."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize LastFM Options flow."""
        super().__init__(dict(entry.data))
        self.entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Initialize form."""
        valid_users = self.data[CONF_USERS]
        errors = {}
        if user_input is not None:
            valid_users = []
            for user in user_input[CONF_USERS]:
                lastfm_user = self._get_lastfm_user(user)
                lastfm_errors = self._validate_lastfm_user(lastfm_user)
                if lastfm_errors:
                    errors = lastfm_errors
                else:
                    valid_users.append(user)
            if not errors:
                await self.hass.config_entries.async_unload(self.entry.entry_id)
                for username in self.data[CONF_USERS]:
                    if username not in user_input[CONF_USERS] and (
                        entity_id := er.async_get(self.hass).async_get_entity_id(
                            Platform.SENSOR, DOMAIN, f"sensor.lastfm_{username}"
                        )
                    ):
                        er.async_get(self.hass).async_remove(entity_id)
                await self.hass.config_entries.async_reload(self.entry.entry_id)
                return self.async_create_entry(
                    title="LastFM",
                    data={
                        **self.data,
                        CONF_USERS: user_input[CONF_USERS],
                    },
                )
        if self.data[CONF_MAIN_USER]:
            try:
                main_user = self._get_lastfm_user(self.data[CONF_MAIN_USER])
                friends: Sequence[SelectOptionDict] = [
                    {"value": str(friend.name), "label": str(friend.get_name(True))}
                    for friend in main_user.get_friends()
                ]
            except WSError:
                friends = []
        else:
            friends = []
        return self.async_show_form(
            step_id="init",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERS, default=valid_users): SelectSelector(
                        SelectSelectorConfig(
                            options=friends, custom_value=True, multiple=True
                        )
                    ),
                }
            ),
        )
