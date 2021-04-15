"""Home Assistant auth provider."""
from __future__ import annotations

import asyncio
import base64
from collections import OrderedDict
from collections.abc import Mapping
import logging
from typing import Any, cast

import bcrypt
import voluptuous as vol

from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultDict
from homeassistant.exceptions import HomeAssistantError

from . import AUTH_PROVIDER_SCHEMA, AUTH_PROVIDERS, AuthProvider, LoginFlow
from ..models import Credentials, UserMeta

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


class Data:
    """Hold the user data."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the user data store."""
        self.hass = hass
        self._store = hass.helpers.storage.Store(
            STORAGE_VERSION, STORAGE_KEY, private=True
        )
        self._data: dict[str, Any] | None = None
        # Legacy mode will allow usernames to start/end with whitespace
        # and will compare usernames case-insensitive.
        # Remove in 2020 or when we launch 1.0.
        self.is_legacy = False

    @callback
    def normalize_username(self, username: str) -> str:
        """Normalize a username based on the mode."""
        if self.is_legacy:
            return username

        return username.strip().casefold()

    async def async_load(self) -> None:
        """Load stored data."""
        data = await self._store.async_load()

        if data is None:
            data = {"users": []}

        seen: set[str] = set()

        for user in data["users"]:
            username = user["username"]

            # check if we have duplicates
            folded = username.casefold()

            if folded in seen:
                self.is_legacy = True

                logging.getLogger(__name__).warning(
                    "Home Assistant auth provider is running in legacy mode "
                    "because we detected usernames that are case-insensitive"
                    "equivalent. Please change the username: '%s'.",
                    username,
                )

                break

            seen.add(folded)

            # check if we have unstripped usernames
            if username != username.strip():
                self.is_legacy = True

                logging.getLogger(__name__).warning(
                    "Home Assistant auth provider is running in legacy mode "
                    "because we detected usernames that start or end in a "
                    "space. Please change the username: '%s'.",
                    username,
                )

                break

        self._data = data

    @property
    def users(self) -> list[dict[str, str]]:
        """Return users."""
        return self._data["users"]  # type: ignore

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

    def hash_password(  # pylint: disable=no-self-use
        self, password: str, for_storage: bool = False
    ) -> bytes:
        """Encode a password."""
        hashed: bytes = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12))

        if for_storage:
            hashed = base64.b64encode(hashed)
        return hashed

    def add_auth(self, username: str, password: str) -> None:
        """Add a new authenticated user/pass."""
        username = self.normalize_username(username)

        if any(
            self.normalize_username(user["username"]) == username for user in self.users
        ):
            raise InvalidUser

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
            raise InvalidUser

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
            raise InvalidUser

    async def async_save(self) -> None:
        """Save data."""
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

    async def async_login_flow(self, context: dict | None) -> LoginFlow:
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
    ) -> FlowResultDict:
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

        schema: dict[str, type] = OrderedDict()
        schema["username"] = str
        schema["password"] = str

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(schema), errors=errors
        )
