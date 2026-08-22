"""Config flow for LastFm."""

import logging
from typing import Any, override
from urllib.parse import parse_qs, urlparse

from pylast import LastFMNetwork, PyLastError, SessionKeyGenerator, User, WSError
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_API_SECRET,
    CONF_MAIN_USER,
    CONF_SESSION_KEY,
    CONF_USERS,
    DOMAIN,
    ERROR_CODE_LOGIN_REQUIRED,
)
from .coordinator import LastFMConfigEntry

PLACEHOLDERS = {
    "api_account_url": "https://www.last.fm/api/account/create",
    "privacy_settings_url": "https://www.last.fm/settings/privacy",
}

CONF_REDIRECT_URL = "redirect_url"

CONFIG_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Optional(CONF_API_SECRET): str,
        vol.Required(CONF_MAIN_USER): str,
    }
)

_LOGGER = logging.getLogger(__name__)


def get_lastfm_user(api_key: str, username: str) -> tuple[User, dict[str, str]]:
    """Get and validate lastFM User."""
    user = LastFMNetwork(api_key=api_key).get_user(username)
    errors = {}
    try:
        user.get_playcount()
        user.get_recent_tracks(limit=1)
    except WSError as error:
        if error.status == ERROR_CODE_LOGIN_REQUIRED:
            errors["base"] = "hidden_recent_tracks"
        elif error.details == "User not found":
            errors["base"] = "invalid_account"
        elif (
            error.details
            == "Invalid API key - You must be granted a valid key by last.fm"
        ):
            errors["base"] = "invalid_auth"
        else:
            errors["base"] = "unknown"
    except Exception:
        _LOGGER.exception("Unexpected exception")
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


def get_user_friends(api_key: str, username: str) -> list[User]:
    """Get the friends of a Last.fm user."""
    user, _ = get_lastfm_user(api_key, username)
    return user.get_friends()


def get_web_auth_url(api_key: str, api_secret: str) -> tuple[SessionKeyGenerator, str]:
    """Start web authentication and return the session key generator and auth URL."""
    session_key_generator = SessionKeyGenerator(
        LastFMNetwork(api_key=api_key, api_secret=api_secret)
    )
    return session_key_generator, session_key_generator.get_web_auth_url()


class LastFmConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow handler for LastFm."""

    data: dict[str, Any] = {}
    _auth_url: str
    _session_key_generator: SessionKeyGenerator

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: LastFMConfigEntry,
    ) -> LastFmOptionsFlowHandler:
        """Get the options flow for this handler."""
        return LastFmOptionsFlowHandler()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Initialize user input."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.data = user_input.copy()
            if not self.data.get(CONF_API_SECRET):
                self.data.pop(CONF_API_SECRET, None)
            _, errors = await self.hass.async_add_executor_job(
                get_lastfm_user, self.data[CONF_API_KEY], self.data[CONF_MAIN_USER]
            )
            if not errors:
                if CONF_API_SECRET in self.data:
                    try:
                        (
                            self._session_key_generator,
                            self._auth_url,
                        ) = await self.hass.async_add_executor_job(
                            get_web_auth_url,
                            self.data[CONF_API_KEY],
                            self.data[CONF_API_SECRET],
                        )
                    except WSError:
                        errors["base"] = "invalid_auth"
                    except Exception:
                        _LOGGER.exception("Unexpected exception")
                        errors["base"] = "unknown"
                    else:
                        return await self.async_step_auth_url()
                else:
                    return await self.async_step_friends()
        return self.async_show_form(
            step_id="user",
            errors=errors,
            description_placeholders=PLACEHOLDERS,
            data_schema=self.add_suggested_values_to_schema(CONFIG_SCHEMA, user_input),
        )

    async def async_step_auth_url(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the web authorization step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            token = parse_qs(urlparse(user_input[CONF_REDIRECT_URL]).query).get(
                "token", [None]
            )[0]
            if token is None:
                errors["base"] = "invalid_url"
            else:
                try:
                    session_key, _username = await self.hass.async_add_executor_job(
                        self._session_key_generator.get_web_auth_session_key_username,
                        "",
                        token,
                    )
                except WSError:
                    errors["base"] = "invalid_auth"
                except Exception:
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"
                else:
                    self.data[CONF_SESSION_KEY] = session_key
                    return await self.async_step_friends()
        return self.async_show_form(
            step_id="auth_url",
            errors=errors,
            description_placeholders={"auth_url": self._auth_url, **PLACEHOLDERS},
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REDIRECT_URL): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.URL)
                    ),
                }
            ),
        )

    async def async_step_friends(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Form to select other users and friends."""
        errors: dict[str, str] = {}
        if user_input is not None:
            users, errors = await self.hass.async_add_executor_job(
                validate_lastfm_users,
                self.data[CONF_API_KEY],
                user_input[CONF_USERS],
            )
            user_input[CONF_USERS] = users
            if not errors:
                options = {
                    CONF_API_KEY: self.data[CONF_API_KEY],
                    CONF_MAIN_USER: self.data[CONF_MAIN_USER],
                    CONF_USERS: [
                        self.data[CONF_MAIN_USER],
                        *user_input[CONF_USERS],
                    ],
                }
                if CONF_SESSION_KEY in self.data:
                    options[CONF_API_SECRET] = self.data[CONF_API_SECRET]
                    options[CONF_SESSION_KEY] = self.data[CONF_SESSION_KEY]
                return self.async_create_entry(
                    title="LastFM",
                    data={},
                    options=options,
                )
        try:
            friends_response = await self.hass.async_add_executor_job(
                get_user_friends, self.data[CONF_API_KEY], self.data[CONF_MAIN_USER]
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
            description_placeholders=PLACEHOLDERS,
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


class LastFmOptionsFlowHandler(OptionsFlowWithReload):
    """LastFm Options flow handler."""

    config_entry: LastFMConfigEntry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Initialize form."""
        errors: dict[str, str] = {}
        options = self.config_entry.options
        if user_input is not None:
            users, errors = await self.hass.async_add_executor_job(
                validate_lastfm_users,
                options[CONF_API_KEY],
                user_input[CONF_USERS],
            )
            user_input[CONF_USERS] = users
            if not errors:
                return self.async_create_entry(
                    title="LastFM",
                    data={
                        **options,
                        CONF_USERS: user_input[CONF_USERS],
                    },
                )
        if options[CONF_MAIN_USER]:
            try:
                friends_response = await self.hass.async_add_executor_job(
                    get_user_friends,
                    options[CONF_API_KEY],
                    options[CONF_MAIN_USER],
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
            description_placeholders=PLACEHOLDERS,
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
                user_input or options,
            ),
        )
