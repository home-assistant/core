"""Config flow for LastFm."""

import asyncio
from functools import partial
import logging
from typing import Any, override

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
)

from .const import (
    CONF_API_SECRET,
    CONF_MAIN_USER,
    CONF_SESSION_KEY,
    CONF_USERS,
    DOMAIN,
    ERROR_CODE_LOGIN_REQUIRED,
    MAX_POLLING_ATTEMPTS,
    POLLING_INTERVAL,
)
from .coordinator import LastFMConfigEntry, get_lastfm_error

PLACEHOLDERS = {
    "api_account_url": "https://www.last.fm/api/account/create",
    "privacy_settings_url": "https://www.last.fm/settings/privacy",
}

CONFIG_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Optional(CONF_API_SECRET): str,
        vol.Required(CONF_MAIN_USER): str,
    }
)

_LOGGER = logging.getLogger(__name__)


def get_lastfm_user(
    api_key: str, username: str, check_recent_tracks: bool = True
) -> tuple[User, dict[str, str]]:
    """Get and validate lastFM User."""
    user = LastFMNetwork(api_key=api_key).get_user(username)
    errors = {}
    try:
        user.get_playcount()
        if check_recent_tracks:
            user.get_recent_tracks(limit=1)
    except PyLastError as error:
        ws_error = get_lastfm_error(error)
        if ws_error is not None and ws_error.status == ERROR_CODE_LOGIN_REQUIRED:
            errors["base"] = "hidden_recent_tracks"
        elif ws_error is not None and ws_error.details == "User not found":
            errors["base"] = "invalid_account"
        elif (
            ws_error is not None
            and ws_error.details
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


def get_session_key(
    session_key_generator: SessionKeyGenerator, auth_url: str
) -> str | None:
    """Exchange the web auth token for a session key once it is authorized."""
    try:
        return session_key_generator.get_web_auth_session_key(auth_url)
    except PyLastError:
        return None
    except Exception:
        _LOGGER.exception("Unexpected exception")
        return None


class LastFmConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow handler for LastFm."""

    data: dict[str, Any] = {}
    _auth_url: str
    _session_key_generator: SessionKeyGenerator
    _polling_task: asyncio.Task[None] | None = None

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: LastFMConfigEntry,
    ) -> LastFmOptionsFlowHandler:
        """Get the options flow for this handler."""
        return LastFmOptionsFlowHandler()

    @callback
    @override
    def async_remove(self) -> None:
        """Cancel the session key polling task when the flow is removed."""
        if self._polling_task:
            self._polling_task.cancel()

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
                partial(
                    get_lastfm_user,
                    self.data[CONF_API_KEY],
                    self.data[CONF_MAIN_USER],
                    check_recent_tracks=CONF_API_SECRET not in self.data,
                )
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
        """Wait for the user to authorize the application on Last.fm."""
        if CONF_SESSION_KEY not in self.data:
            if self._polling_task is None:
                self._polling_task = self.hass.async_create_task(
                    self._async_poll_for_session_key()
                )
            else:
                # The user continued manually before authorization was detected
                session_key = await self.hass.async_add_executor_job(
                    get_session_key, self._session_key_generator, self._auth_url
                )
                if session_key is not None:
                    self.data[CONF_SESSION_KEY] = session_key
        if CONF_SESSION_KEY in self.data:
            if self._polling_task:
                self._polling_task.cancel()
                self._polling_task = None
            return self.async_external_step_done(next_step_id="friends")
        return self.async_external_step(step_id="auth_url", url=self._auth_url)

    async def _async_poll_for_session_key(self) -> None:
        """Poll Last.fm until the user has authorized the application."""
        for _attempt in range(1, MAX_POLLING_ATTEMPTS + 1):
            await asyncio.sleep(POLLING_INTERVAL)
            session_key = await self.hass.async_add_executor_job(
                get_session_key, self._session_key_generator, self._auth_url
            )
            if session_key is not None:
                self.data[CONF_SESSION_KEY] = session_key
                self.hass.async_create_task(
                    self.hass.config_entries.flow.async_configure(self.flow_id)
                )
                return

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
