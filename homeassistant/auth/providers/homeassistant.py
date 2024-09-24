"""Home Assistant auth provider."""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Mapping
import logging
from typing import Any, cast

import bcrypt
import voluptuous as vol

from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store

from ..models import AuthFlowResult, Credentials, UserMeta
from . import AUTH_PROVIDER_SCHEMA, AUTH_PROVIDERS, AuthProvider, LoginFlow

STORAGE_VERSION = 1
STORAGE_KEY = "auth_provider.homeassistant"


def _disallow_id(conf: dict[str, Any]) -> dict[str, Any]:
    """Disallow ID in config."""
    if CONF_ID in conf:
        raise vol.Invalid("ID is not allowed for the homeassistant auth provider.")

    return conf


CONFIG_SCHEMA = vol.All(AUTH_PROVIDER_SCHEMA, _disallow_id)


@callback
def async_get_provider(hass: HomeAssistant) -> HassAuthProvider:
    """Get the provider."""
    for prv in hass.auth.auth_providers:
        if prv.type == "homeassistant":
            return cast(HassAuthProvider, prv)

    raise RuntimeError("Provider not found")


class InvalidAuth(HomeAssistantError):
    """Raised when we encounter invalid authentication."""


class InvalidUser(HomeAssistantError):
    """Raised when invalid user is specified.

    Will not be raised when validating authentication.
    """

    def __init__(
        self,
        *args: object,
        translation_key: str | None = None,
        translation_placeholders: dict[str, str] | None = None,
    ) -> None:
        """Initialize exception."""
        super().__init__(
            *args,
            translation_domain="auth",
            translation_key=translation_key,
            translation_placeholders=translation_placeholders,
        )


class InvalidUsername(InvalidUser):
    """Raised when invalid username is specified.

    Will not be raised when validating authentication.
    """


class Data:
    """Hold the user data."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the user data store."""
        self.hass = hass
        self._store = Store[dict[str, list[dict[str, str]]]](
            hass, STORAGE_VERSION, STORAGE_KEY, private=True, atomic_writes=True
        )
        self._data: dict[str, list[dict[str, str]]] | None = None
        # Legacy mode will allow usernames to start/end with whitespace
        # and will compare usernames case-insensitive.
        # Deprecated in June 2019 and will be removed in 2026.7
        self.is_legacy = False

    @callback
    def normalize_username(
        self, username: str, *, force_normalize: bool = False
    ) -> str:
        """Normalize a username based on the mode."""
        if self.is_legacy and not force_normalize:
            return username

        return username.strip().casefold()

    async def async_load(self) -> None:
        """Load stored data."""
        if (data := await self._store.async_load()) is None:
            data = cast(dict[str, list[dict[str, str]]], {"users": []})

        self._async_check_for_not_normalized_usernames(data)
        self._data = data

    @callback
    def _async_check_for_not_normalized_usernames(
        self, data: dict[str, list[dict[str, str]]]
    ) -> None:
        not_normalized_usernames: set[str] = set()

        for user in data["users"]:
            username = user["username"]

            if self.normalize_username(username, force_normalize=True) != username:
                logging.getLogger(__name__).warning(
                    (
                        "Home Assistant auth provider is running in legacy mode "
                        "because we detected usernames that are normalized (lowercase and without spaces)."
                        " Please change the username: '%s'."
                    ),
                    username,
                )
                not_normalized_usernames.add(username)

        if not_normalized_usernames:
            self.is_legacy = True
            ir.async_create_issue(
                self.hass,
                "auth",
                "homeassistant_provider_not_normalized_usernames",
                breaks_in_ha_version="2026.7.0",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="homeassistant_provider_not_normalized_usernames",
                translation_placeholders={
                    "usernames": f'- "{'"\n- "'.join(sorted(not_normalized_usernames))}"'
                },
                learn_more_url="homeassistant://config/users",
            )
        else:
            self.is_legacy = False
            ir.async_delete_issue(
                self.hass, "auth", "homeassistant_provider_not_normalized_usernames"
            )

    @property
    def users(self) -> list[dict[str, str]]:
        """Return users."""
        assert self._data is not None
        return self._data["users"]

    def validate_login(self, username: str, password: str) -> None:
        """Validate a username and password.

        Raises InvalidAuth if auth invalid.
        """
        username = self.normalize_username(username)
        dummy = b"$2b$12$CiuFGszHx9eNHxPuQcwBWez4CwDTOcLTX5CbOpV6gef2nYuXkY7BO"
        found = None

        # Compare all users to avoid timing attacks.
        for user in self.users:
            if self.normalize_username(user["username"]) == username:
                found = user

        if found is None:
            # check a hash to make timing the same as if user was found
            bcrypt.checkpw(b"foo", dummy)
            raise InvalidAuth

        user_hash = base64.b64decode(found["password"])

        # bcrypt.checkpw is timing-safe
        if not bcrypt.checkpw(password.encode(), user_hash):
            raise InvalidAuth

    def hash_password(self, password: str, for_storage: bool = False) -> bytes:
        """Encode a password."""
        hashed: bytes = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12))

        if for_storage:
            hashed = base64.b64encode(hashed)
        return hashed

    def add_auth(self, username: str, password: str) -> None:
        """Add a new authenticated user/pass.

        Raises InvalidUsername if the new username is invalid.
        """
        self._validate_new_username(username)

        self.users.append(
            {
                "username": username,
                "password": self.hash_password(password, True).decode(),
            }
        )

    @callback
    def async_remove_auth(self, username: str) -> None:
        """Remove authentication."""
        username = self.normalize_username(username)

        index = None
        for i, user in enumerate(self.users):
            if self.normalize_username(user["username"]) == username:
                index = i
                break

        if index is None:
            raise InvalidUser(translation_key="user_not_found")

        self.users.pop(index)

    def change_password(self, username: str, new_password: str) -> None:
        """Update the password.

        Raises InvalidUser if user cannot be found.
        """
        username = self.normalize_username(username)

        for user in self.users:
            if self.normalize_username(user["username"]) == username:
                user["password"] = self.hash_password(new_password, True).decode()
                break
        else:
            raise InvalidUser(translation_key="user_not_found")

    @callback
    def _validate_new_username(self, new_username: str) -> None:
        """Validate that username is normalized and unique.

        Raises InvalidUsername if the new username is invalid.
        """
        normalized_username = self.normalize_username(
            new_username, force_normalize=True
        )
        if normalized_username != new_username:
            raise InvalidUsername(
                translation_key="username_not_normalized",
                translation_placeholders={"new_username": new_username},
            )

        if any(
            self.normalize_username(user["username"]) == normalized_username
            for user in self.users
        ):
            raise InvalidUsername(
                translation_key="username_already_exists",
                translation_placeholders={"username": new_username},
            )

    @callback
    def change_username(self, username: str, new_username: str) -> None:
        """Update the username.

        Raises InvalidUser if user cannot be found.
        Raises InvalidUsername if the new username is invalid.
        """
        username = self.normalize_username(username)
        self._validate_new_username(new_username)

        for user in self.users:
            if self.normalize_username(user["username"]) == username:
                user["username"] = new_username
                assert self._data is not None
                self._async_check_for_not_normalized_usernames(self._data)
                break
        else:
            raise InvalidUser(translation_key="user_not_found")

    async def async_save(self) -> None:
        """Save data."""
        if self._data is not None:
            await self._store.async_save(self._data)


@AUTH_PROVIDERS.register("homeassistant")
class HassAuthProvider(AuthProvider):
    """Auth provider based on a local storage of users in Home Assistant config dir."""

    DEFAULT_TITLE = "Home Assistant Local"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize an Home Assistant auth provider."""
        super().__init__(*args, **kwargs)
        self.data: Data | None = None
        self._init_lock = asyncio.Lock()

    async def async_initialize(self) -> None:
        """Initialize the auth provider."""
        async with self._init_lock:
            if self.data is not None:
                return

            data = Data(self.hass)
            await data.async_load()
            self.data = data

    async def async_login_flow(self, context: dict[str, Any] | None) -> LoginFlow:
        """Return a flow to login."""
        return HassLoginFlow(self)

    async def async_validate_login(self, username: str, password: str) -> None:
        """Validate a username and password."""
        if self.data is None:
            await self.async_initialize()
            assert self.data is not None

        await self.hass.async_add_executor_job(
            self.data.validate_login, username, password
        )

    async def async_add_auth(self, username: str, password: str) -> None:
        """Call add_auth on data."""
        if self.data is None:
            await self.async_initialize()
            assert self.data is not None

        await self.hass.async_add_executor_job(self.data.add_auth, username, password)
        await self.data.async_save()

    async def async_remove_auth(self, username: str) -> None:
        """Call remove_auth on data."""
        if self.data is None:
            await self.async_initialize()
            assert self.data is not None

        self.data.async_remove_auth(username)
        await self.data.async_save()

    async def async_change_password(self, username: str, new_password: str) -> None:
        """Call change_password on data."""
        if self.data is None:
            await self.async_initialize()
            assert self.data is not None

        await self.hass.async_add_executor_job(
            self.data.change_password, username, new_password
        )
        await self.data.async_save()

    async def async_change_username(
        self, credential: Credentials, new_username: str
    ) -> None:
        """Validate new username and change it including updating credentials object."""
        if self.data is None:
            await self.async_initialize()
            assert self.data is not None

        self.data.change_username(credential.data["username"], new_username)
        self.hass.auth.async_update_user_credentials_data(
            credential, {**credential.data, "username": new_username}
        )
        await self.data.async_save()

    async def async_get_or_create_credentials(
        self, flow_result: Mapping[str, str]
    ) -> Credentials:
        """Get credentials based on the flow result."""
        if self.data is None:
            await self.async_initialize()
            assert self.data is not None

        norm_username = self.data.normalize_username
        username = norm_username(flow_result["username"])

        for credential in await self.async_credentials():
            if norm_username(credential.data["username"]) == username:
                return credential

        # Create new credentials.
        return self.async_create_credentials({"username": username})

    async def async_user_meta_for_credentials(
        self, credentials: Credentials
    ) -> UserMeta:
        """Get extra info for this credential."""
        return UserMeta(name=credentials.data["username"], is_active=True)

    async def async_will_remove_credentials(self, credentials: Credentials) -> None:
        """When credentials get removed, also remove the auth."""
        if self.data is None:
            await self.async_initialize()
            assert self.data is not None

        try:
            self.data.async_remove_auth(credentials.data["username"])
            await self.data.async_save()
        except InvalidUser:
            # Can happen if somehow we didn't clean up a credential
            pass


class HassLoginFlow(LoginFlow):
    """Handler for the login flow."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> AuthFlowResult:
        """Handle the step of the form."""
        errors = {}

        if user_input is not None:
            try:
                await cast(HassAuthProvider, self._auth_provider).async_validate_login(
                    user_input["username"], user_input["password"]
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"

            if not errors:
                user_input.pop("password")
                return await self.async_finish(user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("username"): str,
                    vol.Required("password"): str,
                }
            ),
            errors=errors,
        )
