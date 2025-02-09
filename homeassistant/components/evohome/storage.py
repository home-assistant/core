"""Support for (EMEA/EU-based) Honeywell TCC systems."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, NotRequired, TypedDict

from evohomeasync.auth import (
    SZ_SESSION_ID,
    SZ_SESSION_ID_EXPIRES,
    AbstractSessionManager,
)
from evohomeasync2.auth import AbstractTokenManager

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VER


class _SessionIdEntryT(TypedDict):
    session_id: str
    session_id_expires: NotRequired[str]  # dt.isoformat()  # TZ-aware


class _TokenStoreT(TypedDict):
    username: str
    refresh_token: str
    access_token: str
    access_token_expires: str  # dt.isoformat()  # TZ-aware
    session_id: NotRequired[str]
    session_id_expires: NotRequired[str]  # dt.isoformat()  # TZ-aware


class TokenManager(AbstractTokenManager, AbstractSessionManager):
    """A token manager that uses a cache file to store the tokens."""

    def __init__(
        self,
        hass: HomeAssistant,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialise the token manager."""
        super().__init__(*args, **kwargs)

        self._store = Store(hass, STORAGE_VER, STORAGE_KEY)  # type: ignore[var-annotated]
        self._store_initialized = False  # True once cache loaded first time

    async def get_access_token(self) -> str:
        """Return a valid access token.

        If the cached entry is not valid, will fetch a new access token.
        """

        if not self._store_initialized:
            await self._load_cache_from_store()

        return await super().get_access_token()

    async def get_session_id(self) -> str:
        """Return a valid session id.

        If the cached entry is not valid, will fetch a new session id.
        """

        if not self._store_initialized:
            await self._load_cache_from_store()

        return await super().get_session_id()

    async def _load_cache_from_store(self) -> None:
        """Load the user entry from the cache.

        Assumes single reader/writer. Reads only once, at initialization.
        """

        cache: _TokenStoreT = await self._store.async_load() or {}  # type: ignore[assignment]
        self._store_initialized = True

        if not cache or cache["username"] != self._client_id:
            return

        if SZ_SESSION_ID in cache:
            self._import_session_id(cache)  # type: ignore[arg-type]
        self._import_access_token(cache)

    def _import_session_id(self, session: _SessionIdEntryT) -> None:  # type: ignore[override]
        """Extract the session id from a (serialized) dictionary."""
        # base class method overridden because session_id_expired is NotRequired here

        self._session_id = session[SZ_SESSION_ID]

        session_id_expires = session.get(SZ_SESSION_ID_EXPIRES)
        if session_id_expires is None:
            self._session_id_expires = datetime.now(tz=UTC) + timedelta(minutes=15)
        else:
            self._session_id_expires = datetime.fromisoformat(session_id_expires)

    async def save_access_token(self) -> None:  # an abstractmethod
        """Save the access token (and expiry dtm, refresh token) to the cache."""
        await self.save_cache_to_store()

    async def save_session_id(self) -> None:  # an abstractmethod
        """Save the session id (and expiry dtm) to the cache."""
        await self.save_cache_to_store()

    async def save_cache_to_store(self) -> None:
        """Save the access token (and session id, if any) to the cache.

        Assumes a single reader/writer. Writes whenever new data has been fetched.
        """

        cache = {"username": self._client_id} | self._export_access_token()
        if self._session_id:
            cache |= self._export_session_id()

        await self._store.async_save(cache)
