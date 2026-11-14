"""Support for (EMEA/EU-based) Honeywell TCC systems."""

from datetime import timedelta
from typing import Any, NotRequired, TypedDict, override

from evohomeasync.auth import (
    SZ_SESSION_ID,
    SZ_SESSION_ID_EXPIRES,
    AbstractSessionManager,
)
from evohomeasync2.auth import AbstractTokenManager

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import STORAGE_KEY, STORAGE_VER


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

        self._store: Store[_TokenStoreT] = Store(hass, STORAGE_VER, STORAGE_KEY)
        self._store_initialized = False  # True once cache loaded first time

    @override
    async def get_access_token(self) -> str:
        """Return a valid access token.

        If the cached entry is not valid, will fetch a new access token.
        """

        if not self._store_initialized:
            await self._load_cache_from_store()

        return await super().get_access_token()

    @override
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

        cache = await self._store.async_load()
        self._store_initialized = True

        if not cache or cache["username"] != self.client_id:
            return

        if SZ_SESSION_ID in cache:
            # older caches may not have stored when the session id expires
            session_id_expires = cache.get(SZ_SESSION_ID_EXPIRES) or (
                (dt_util.utcnow() + timedelta(minutes=15)).isoformat()
            )
            self.import_session_id(
                {
                    SZ_SESSION_ID: cache[SZ_SESSION_ID],
                    SZ_SESSION_ID_EXPIRES: session_id_expires,
                }
            )
        self.import_access_token(cache)

    @override
    async def save_access_token(self) -> None:  # an abstractmethod
        """Save the access token (and expiry dtm, refresh token) to the cache."""
        await self.save_cache_to_store()

    @override
    async def save_session_id(self) -> None:  # an abstractmethod
        """Save the session id (and expiry dtm) to the cache."""
        await self.save_cache_to_store()

    async def save_cache_to_store(self) -> None:
        """Save the access token (and session id, if any) to the cache.

        Assumes a single reader/writer. Writes whenever new data has been fetched.
        """

        cache: _TokenStoreT = {
            "username": self.client_id,
            **self.export_access_token(),
        }
        if self.session_id:
            cache.update(self.export_session_id())

        await self._store.async_save(cache)
