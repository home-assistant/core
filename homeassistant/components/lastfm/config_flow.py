"""Config flow for LastFm."""

import asyncio
from collections.abc import Mapping
from functools import partial
import logging
from typing import Any, override

from pylast import (
    LastFMNetwork,
    MalformedResponseError,
    NetworkError,
    PyLastError,
    SessionKeyGenerator,
    User,
    WSError,
)
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
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
    ERROR_CODE_TOKEN_UNAUTHORIZED,
    ERROR_CODES_INVALID_AUTH,
    ERROR_CODES_RETRYABLE,
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
        vol.Optional(CONF_API_SECRET): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Required(CONF_MAIN_USER): str,
    }
)

_LOGGER = logging.getLogger(__name__)


def get_lastfm_user(
    api_key: str,
    username: str,
    check_recent_tracks: bool = True,
    api_secret: str = "",
    session_key: str = "",
) -> tuple[User, dict[str, str]]:
    """Get and validate lastFM User."""
    user = LastFMNetwork(
        api_key=api_key, api_secret=api_secret, session_key=session_key
    ).get_user(username)
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
    api_key: str,
    usernames: list[str],
    api_secret: str = "",
    session_key: str = "",
) -> tuple[list[str], dict[str, str]]:
    """Validate list of users. Return tuple of valid users and errors."""
    valid_users = []
    errors = {}
    for username in usernames:
        _, lastfm_errors = get_lastfm_user(
            api_key,
            username,
            api_secret=api_secret,
            session_key=session_key,
        )
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
) -> tuple[str, str] | None:
    """Exchange the web auth token for a session key and username."""
    try:
        return session_key_generator.get_web_auth_session_key_username(auth_url)
    except PyLastError as error:
        ws_error = get_lastfm_error(error)
        if (
            ws_error is not None
            and str(ws_error.status)
            in {ERROR_CODE_TOKEN_UNAUTHORIZED, *ERROR_CODES_RETRYABLE}
        ) or isinstance(error, (MalformedResponseError, NetworkError)):
            return None
        raise


class LastFmConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow handler for LastFm."""

    data: dict[str, Any] = {}
    _auth_url: str
    _authorized_username: str | None = None
    _session_key_error: bool = False
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
            self._polling_task = None

    @callback
    def _set_session(self, session: tuple[str, str]) -> None:
        """Store a session when it belongs to the configured user."""
        session_key, username = session
        self._authorized_username = username
        if username.casefold() == self.data[CONF_MAIN_USER].casefold():
            self.data[CONF_SESSION_KEY] = session_key

    async def _async_get_session_key(self) -> tuple[str, str] | None:
        """Get the session key and record terminal exchange failures."""
        try:
            return await self.hass.async_add_executor_job(
                get_session_key, self._session_key_generator, self._auth_url
            )
        except PyLastError:
            self._session_key_error = True
        except Exception:
            _LOGGER.exception("Unexpected exception")
            self._session_key_error = True
        return None

    async def _async_start_web_auth(self) -> str | None:
        """Start Last.fm web authentication and return an error key on failure."""
        try:
            (
                self._session_key_generator,
                self._auth_url,
            ) = await self.hass.async_add_executor_job(
                get_web_auth_url,
                self.data[CONF_API_KEY],
                self.data[CONF_API_SECRET],
            )
        except MalformedResponseError, NetworkError:
            return "cannot_connect"
        except WSError as error:
            status = str(error.status)
            if status in ERROR_CODES_RETRYABLE:
                return "cannot_connect"
            if status in ERROR_CODES_INVALID_AUTH:
                return "invalid_auth"
            return "unknown"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return "unknown"
        return None

    async def _async_start_reauth(self) -> ConfigFlowResult:
        """Start reauthentication or show a retryable connection error."""
        if (error := await self._async_start_web_auth()) == "cannot_connect":
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
                errors={"base": error},
            )
        if error is not None:
            return self.async_abort(reason="auth_failed")
        return await self.async_step_auth_url()

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
                    if (error := await self._async_start_web_auth()) is None:
                        return await self.async_step_auth_url()
                    errors["base"] = error
                else:
                    return await self.async_step_friends()
        return self.async_show_form(
            step_id="user",
            errors=errors,
            description_placeholders=PLACEHOLDERS,
            data_schema=self.add_suggested_values_to_schema(CONFIG_SCHEMA, user_input),
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication for an invalid Last.fm session."""
        options = self._get_reauth_entry().options
        self.data = {
            CONF_API_KEY: options[CONF_API_KEY],
            CONF_API_SECRET: options[CONF_API_SECRET],
            CONF_MAIN_USER: options[CONF_MAIN_USER],
        }
        return await self._async_start_reauth()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Retry starting Last.fm reauthentication."""
        return await self._async_start_reauth()

    async def async_step_auth_url(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Wait for the user to authorize the application on Last.fm."""
        if not self._session_key_error and CONF_SESSION_KEY not in self.data:
            if self._polling_task is None:
                self._polling_task = self.hass.async_create_background_task(
                    self._async_poll_for_session_key(),
                    "Polling Last.fm authorization",
                    eager_start=False,
                )
            else:
                # The user continued manually before authorization was detected
                session = await self._async_get_session_key()
                if session is not None:
                    self._set_session(session)
        if self._session_key_error:
            if self._polling_task:
                self._polling_task.cancel()
                self._polling_task = None
            return self.async_external_step_done(next_step_id="auth_failed")
        if self._authorized_username is not None and CONF_SESSION_KEY not in self.data:
            if self._polling_task:
                self._polling_task.cancel()
                self._polling_task = None
            return self.async_external_step_done(next_step_id="wrong_account")
        if CONF_SESSION_KEY in self.data:
            if self._polling_task:
                self._polling_task.cancel()
                self._polling_task = None
            return self.async_external_step_done(
                next_step_id=(
                    "finish_reauth" if self.source == SOURCE_REAUTH else "friends"
                )
            )
        return self.async_external_step(step_id="auth_url", url=self._auth_url)

    async def async_step_finish_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Save the replacement Last.fm session key."""
        reauth_entry = self._get_reauth_entry()
        return self.async_update_reload_and_abort(
            reauth_entry,
            options={
                **reauth_entry.options,
                CONF_SESSION_KEY: self.data[CONF_SESSION_KEY],
            },
        )

    async def async_step_auth_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abort after a terminal Last.fm authorization failure."""
        return self.async_abort(reason="auth_failed")

    async def async_step_wrong_account(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abort when authorization used a different Last.fm account."""
        assert self._authorized_username is not None
        return self.async_abort(
            reason="wrong_account",
            description_placeholders={
                "authorized_user": self._authorized_username,
                "configured_user": self.data[CONF_MAIN_USER],
            },
        )

    async def _async_poll_for_session_key(self) -> None:
        """Poll Last.fm until the user has authorized the application."""
        try:
            for _attempt in range(1, MAX_POLLING_ATTEMPTS + 1):
                await asyncio.sleep(POLLING_INTERVAL)
                session = await self._async_get_session_key()
                if self._session_key_error:
                    self._polling_task = None
                    self.hass.async_create_task(
                        self.hass.config_entries.flow.async_configure(self.flow_id)
                    )
                    return
                if session is not None:
                    self._set_session(session)
                    self._polling_task = None
                    self.hass.async_create_task(
                        self.hass.config_entries.flow.async_configure(self.flow_id)
                    )
                    return
        finally:
            self._polling_task = None

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
                partial(
                    validate_lastfm_users,
                    options[CONF_API_KEY],
                    user_input[CONF_USERS],
                    api_secret=options.get(CONF_API_SECRET, ""),
                    session_key=options.get(CONF_SESSION_KEY, ""),
                )
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
