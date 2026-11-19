"""Config flow for LastFm."""

from contextlib import suppress
import logging
from typing import Any, override
from urllib.parse import parse_qs, urlparse

import probatio
from pylast import LastFMNetwork, PyLastError, SessionKeyGenerator, User, WSError

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_API_KEY, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import (
    CONF_API_SECRET,
    CONF_MAIN_USER,
    CONF_SESSION_KEYS,
    CONF_USERS,
    DOMAIN,
    ERROR_CODE_LOGIN_REQUIRED,
)
from .coordinator import LastFMConfigEntry

PLACEHOLDERS = {
    "api_account_url": "https://www.last.fm/api/account/create",
    "privacy_settings_url": "https://www.last.fm/settings/privacy",
}

CONFIG_SCHEMA: probatio.Schema = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_API_KEY)): str,
        probatio.Required(CONF_MAIN_USER): str,
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


def get_user_friends(api_key: str, username: str) -> list[str]:
    """Get the usernames of the friends of a Last.fm user."""
    user, _ = get_lastfm_user(api_key, username)
    return [friend.get_name() for friend in user.get_friends()]


def get_auth_url(api_key: str, api_secret: str) -> str:
    """Request a token and return the URL the user must authorize."""
    network = LastFMNetwork(api_key=api_key, api_secret=api_secret)
    return SessionKeyGenerator(network).get_web_auth_url()


def get_session_key(api_key: str, api_secret: str, auth_url: str) -> tuple[str, str]:
    """Exchange the authorized token for a session key.

    Returns the session key and the name of the account that authorized it.
    """
    network = LastFMNetwork(api_key=api_key, api_secret=api_secret)
    token = parse_qs(urlparse(auth_url).query)["token"][0]
    return SessionKeyGenerator(network).get_web_auth_session_key_username(
        auth_url, token
    )


class LastFmConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow handler for LastFm."""

    data: dict[str, Any] = {}
    _username: str
    _auth_url: str

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
            _, errors = await self.hass.async_add_executor_job(
                get_lastfm_user, self.data[CONF_API_KEY], self.data[CONF_MAIN_USER]
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
            users, errors = await self.hass.async_add_executor_job(
                validate_lastfm_users,
                self.data[CONF_API_KEY],
                user_input[CONF_USERS],
            )
            user_input[CONF_USERS] = users
            if not errors:
                self.data[CONF_USERS] = [
                    self.data[CONF_MAIN_USER],
                    *user_input[CONF_USERS],
                ]
                self.data[CONF_SESSION_KEYS] = {}
                return await self.async_step_scrobble_menu()
        friends: list[str] = []
        with suppress(PyLastError):
            friends = await self.hass.async_add_executor_job(
                get_user_friends, self.data[CONF_API_KEY], self.data[CONF_MAIN_USER]
            )
        return self.async_show_form(
            step_id="friends",
            errors=errors,
            description_placeholders=PLACEHOLDERS,
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required(CONF_USERS): SelectSelector(
                            SelectSelectorConfig(
                                options=friends, custom_value=True, multiple=True
                            )
                        ),
                    }
                ),
                user_input or {CONF_USERS: []},
            ),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start the scrobbling setup for an existing entry."""
        self.data = dict(self._get_reconfigure_entry().options)
        self.data.setdefault(CONF_SESSION_KEYS, {})
        return await self.async_step_scrobble_menu()

    async def async_step_scrobble_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user authorize users for scrobbling, or finish."""
        return self.async_show_menu(
            step_id="scrobble_menu",
            menu_options=["scrobble_user", "finish"],
            description_placeholders={
                "authorized_users": ", ".join(
                    f"**{user}**" for user in self.data[CONF_SESSION_KEYS]
                )
                or "–"
            },
        )

    async def async_step_scrobble_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick a user to authorize for scrobbling."""
        stored_secret = self.data.get(CONF_API_SECRET)
        if user_input is not None:
            api_secret: str = (
                user_input.get(CONF_API_SECRET) or self.data[CONF_API_SECRET]
            )
            try:
                self._auth_url = await self.hass.async_add_executor_job(
                    get_auth_url, self.data[CONF_API_KEY], api_secret
                )
            except PyLastError as err:
                _LOGGER.warning("Could not start Last.fm authorization: %s", err)
                return await self.async_step_scrobble_failed()
            self.data[CONF_API_SECRET] = api_secret
            self._username = user_input[CONF_USERNAME]
            return await self.async_step_authorize()

        schema: dict[Any, Any] = {
            probatio.Required(CONF_USERNAME): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(
                            value=user,
                            label=(
                                f"{user} ✓"
                                if user in self.data[CONF_SESSION_KEYS]
                                else user
                            ),
                        )
                        for user in self.data[CONF_USERS]
                    ]
                )
            )
        }
        if stored_secret is None:
            schema[probatio.Required(probatio.Secret(CONF_API_SECRET))] = str
        return self.async_show_form(
            step_id="scrobble_user",
            description_placeholders={
                **PLACEHOLDERS,
                "secret_hint": (
                    ""
                    if stored_secret
                    else "You also need the shared secret from your Last.fm "
                    f"[API account]({PLACEHOLDERS['api_account_url']})."
                ),
            },
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(schema), user_input
            ),
        )

    async def async_step_authorize(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Authorize on Last.fm, then store the session key for this user."""
        if user_input is not None:
            try:
                session_key, account = await self.hass.async_add_executor_job(
                    get_session_key,
                    self.data[CONF_API_KEY],
                    self.data[CONF_API_SECRET],
                    self._auth_url,
                )
            except PyLastError as err:
                _LOGGER.warning("Last.fm authorization failed: %s", err)
                return await self._async_scrobble_failed()
            if account.lower() != self._username.lower():
                _LOGGER.warning(
                    "Authorized Last.fm account %s does not match selected user %s",
                    account,
                    self._username,
                )
                return await self._async_scrobble_failed()
            self.data[CONF_SESSION_KEYS] = {
                **self.data[CONF_SESSION_KEYS],
                self._username: session_key,
            }
            return await self.async_step_scrobble_menu()
        return self.async_show_form(
            step_id="authorize",
            data_schema=probatio.Schema({}),
            description_placeholders={"auth_url": self._auth_url},
        )

    async def _async_scrobble_failed(self) -> ConfigFlowResult:
        """Forget an unproven secret, then show the failure menu."""
        if not self.data[CONF_SESSION_KEYS]:
            # No user was ever authorized, so the secret may be the problem
            self.data.pop(CONF_API_SECRET, None)
        return await self.async_step_scrobble_failed()

    async def async_step_scrobble_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer to retry or go back after a failed authorization."""
        return self.async_show_menu(
            step_id="scrobble_failed",
            menu_options=["scrobble_user", "scrobble_menu"],
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create or update the entry."""
        options = dict(self.data)
        if not options.get(CONF_SESSION_KEYS):
            options.pop(CONF_SESSION_KEYS, None)
            options.pop(CONF_API_SECRET, None)
        if self.source == SOURCE_RECONFIGURE:
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(), options=options
            )
        return self.async_create_entry(title="LastFM", data={}, options=options)


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
                        CONF_SESSION_KEYS: {
                            user: key
                            for user, key in options.get(CONF_SESSION_KEYS, {}).items()
                            if user in user_input[CONF_USERS]
                        },
                    },
                )
        friends: list[str] = []
        if options[CONF_MAIN_USER]:
            with suppress(PyLastError):
                friends = await self.hass.async_add_executor_job(
                    get_user_friends,
                    options[CONF_API_KEY],
                    options[CONF_MAIN_USER],
                )
        return self.async_show_form(
            step_id="init",
            errors=errors,
            description_placeholders=PLACEHOLDERS,
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required(CONF_USERS): SelectSelector(
                            SelectSelectorConfig(
                                options=friends, custom_value=True, multiple=True
                            )
                        ),
                    }
                ),
                user_input or options,
            ),
        )
