"""Config flow for LastFm."""

from __future__ import annotations

from typing import Any

from pylast import LastFMNetwork, PyLastError, User, WSError
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import CONF_MAIN_USER, CONF_USERS, DOMAIN

PLACEHOLDERS = {"api_account_url": "https://www.last.fm/api/account/create"}

CONFIG_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_MAIN_USER): str,
    }
)


def get_lastfm_user(api_key: str, username: str) -> tuple[User, dict[str, str]]:
    """Get and validate lastFM User."""
    user = LastFMNetwork(api_key=api_key).get_user(username)
    errors = {}
    try:
        user.get_playcount()
    except WSError as error:
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
    return user, errors


def validate_lastfm_users(
    api_key: str, usernames: list[str]
) -> tuple[list[str], dict[str, str]]:
    """Validate list of users. Return tuple of valid users and errors."""
    valid_users = []
    errors = {}
    for username in usernames:
        _, lastfm_errors = get_lastfm_user(api_key, username)
        if lastfm_errors:
            errors = lastfm_errors
        else:
            valid_users.append(username)
    return valid_users, errors


class LastFmConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow handler for LastFm."""

    data: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> LastFmOptionsFlowHandler:
        """Get the options flow for this handler."""
        return LastFmOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Initialize user input."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.data = user_input.copy()
            _, errors = get_lastfm_user(
                self.data[CONF_API_KEY], self.data[CONF_MAIN_USER]
            )
            if not errors:
                return await self.async_step_friends()
        return self.async_show_form(
            step_id="user",
            errors=errors,
            description_placeholders=PLACEHOLDERS,
            data_schema=self.add_suggested_values_to_schema(CONFIG_SCHEMA, user_input),
        )

    async def async_step_friends(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Form to select other users and friends."""
        errors: dict[str, str] = {}
        if user_input is not None:
            users, errors = validate_lastfm_users(
                self.data[CONF_API_KEY], user_input[CONF_USERS]
            )
            user_input[CONF_USERS] = users
            if not errors:
                return self.async_create_entry(
                    title="LastFM",
                    data={},
                    options={
                        CONF_API_KEY: self.data[CONF_API_KEY],
                        CONF_MAIN_USER: self.data[CONF_MAIN_USER],
                        CONF_USERS: [
                            self.data[CONF_MAIN_USER],
                            *user_input[CONF_USERS],
                        ],
                    },
                )
        try:
            main_user, _ = get_lastfm_user(
                self.data[CONF_API_KEY], self.data[CONF_MAIN_USER]
            )
            friends_response = await self.hass.async_add_executor_job(
                main_user.get_friends
            )
            friends = [
                SelectOptionDict(value=friend.name, label=friend.get_name(True))
                for friend in friends_response
            ]
        except PyLastError:
            friends = []
        return self.async_show_form(
            step_id="friends",
            errors=errors,
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_USERS): SelectSelector(
                            SelectSelectorConfig(
                                options=friends, custom_value=True, multiple=True
                            )
                        ),
                    }
                ),
                user_input or {CONF_USERS: []},
            ),
        )


class LastFmOptionsFlowHandler(OptionsFlowWithConfigEntry):
    """LastFm Options flow handler."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Initialize form."""
        errors: dict[str, str] = {}
        if user_input is not None:
            users, errors = validate_lastfm_users(
                self.options[CONF_API_KEY], user_input[CONF_USERS]
            )
            user_input[CONF_USERS] = users
            if not errors:
                return self.async_create_entry(
                    title="LastFM",
                    data={
                        **self.options,
                        CONF_USERS: user_input[CONF_USERS],
                    },
                )
        if self.options[CONF_MAIN_USER]:
            try:
                main_user, _ = get_lastfm_user(
                    self.options[CONF_API_KEY],
                    self.options[CONF_MAIN_USER],
                )
                friends_response = await self.hass.async_add_executor_job(
                    main_user.get_friends
                )
                friends = [
                    SelectOptionDict(value=friend.name, label=friend.get_name(True))
                    for friend in friends_response
                ]
            except PyLastError:
                friends = []
        else:
            friends = []
        return self.async_show_form(
            step_id="init",
            errors=errors,
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_USERS): SelectSelector(
                            SelectSelectorConfig(
                                options=friends, custom_value=True, multiple=True
                            )
                        ),
                    }
                ),
                user_input or self.options,
            ),
        )
