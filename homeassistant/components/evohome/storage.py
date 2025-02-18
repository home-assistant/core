"""Support for (EMEA/EU-based) Honeywell TCC systems."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
import logging
from typing import Final, NotRequired

import aiohttp
from evohomeasync.auth import SZ_SESSION_ID, AbstractSessionManager, SessionIdEntryT
from evohomeasync2.auth import (
    SZ_ACCESS_TOKEN,
    SZ_ACCESS_TOKEN_EXPIRES,
    SZ_REFRESH_TOKEN,
    AbstractTokenManager,
)
from evohomeasync2.schemas.typedefs import EvoAuthTokensDictT as AccessTokenEntryT

SZ_CLIENT_ID: Final = "client_id"

DATETIME_MIN_STR: Final = datetime.min.replace(tzinfo=UTC).isoformat()


class TokenDataT(AccessTokenEntryT):
    """The token data as stored in the cache."""

    session_id: NotRequired[str]  # only if high-precision temperatures
    session_id_expires: NotRequired[str]  # dt.isoformat(), TZ-aware


_ACCESS_TOKEN_KEYS = AccessTokenEntryT.__annotations__.keys()
_SESSION_ID_KEYS = SessionIdEntryT.__annotations__.keys()

_NULL_TOKEN_DATA: Final[TokenDataT] = {
    SZ_ACCESS_TOKEN: "",
    SZ_ACCESS_TOKEN_EXPIRES: DATETIME_MIN_STR,
    SZ_REFRESH_TOKEN: "",
}


class TokenManager(AbstractTokenManager, AbstractSessionManager):
    """A token manager that uses a cache to store the tokens.

    Loads only once, at/after initialization. Writes whenever new token data has
    been fetched.
    """

    def __init__(
        self,
        client_id: str,
        secret: str,
        websession: aiohttp.ClientSession,
        /,
        cache_loader: Callable[[str], Awaitable[TokenDataT | None]],
        cache_saver: Callable[[str, TokenDataT], Awaitable[None]],
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialise the token manager."""
        super().__init__(client_id, secret, websession, logger=logger)

        self._store_initialized = False  # True once cache loaded first time

        self._cache_loader = cache_loader
        self._cache_saver = cache_saver

    async def get_access_token(self) -> str:
        """Return a valid access token.

        If the cached entry is not valid, will fetch a new access token.
        """

        if not self._store_initialized:
            await self._load_cache_from_store()

        return await super().get_access_token()

    async def fetch_access_token(self, *, clear_refresh_token: bool = False) -> None:
        """Fetch a new access token from the vendor API.

        Uses the refresh token if available, otherwise the client_id/secret.
        """

        if not self._store_initialized:
            # otherwise, a subsequent get_access_token will be confused
            self._store_initialized = True

        return await super().fetch_access_token()

    async def get_session_id(self) -> str:
        """Return a valid session id.

        If the cached entry is not valid, will fetch a new session id.
        """

        if not self._store_initialized:
            await self._load_cache_from_store()

        return await super().get_session_id()

    async def fetch_session_id(self) -> None:
        """Fetch a new session id from the vendor API."""

        if not self._store_initialized:
            # otherwise, a subsequent get_session_id will be confused
            self._store_initialized = True

        return await super().fetch_session_id()

    async def _load_cache_from_store(self) -> None:
        """Load the access token (and session id, if any) from the store."""

        self._store_initialized = True  # only load the cache once

        token_data = await self._cache_loader(self.client_id)

        if token_data is None:
            token_data = _NULL_TOKEN_DATA

        elif SZ_SESSION_ID in token_data:
            self._import_session_id(
                {k: v for k, v in token_data.items() if k in _SESSION_ID_KEYS}  # type: ignore[arg-type]
            )

        assert token_data is not None  # mypy hint

        self._import_access_token(
            {k: v for k, v in token_data.items() if k in _ACCESS_TOKEN_KEYS}  # type: ignore[arg-type]
        )

    async def save_access_token(self) -> None:  # an abstractmethod
        """Save the access token (and expiry dtm, refresh token) to the cache."""
        await self._save_cache_to_store()

    async def save_session_id(self) -> None:  # an abstractmethod
        """Save the session id (and expiry dtm) to the cache."""
        await self._save_cache_to_store()

    async def _save_cache_to_store(self) -> None:
        """Save the access token (and session id, if any) to the store."""

        token_data: TokenDataT = self._export_access_token()  # type: ignore[assignment]

        if self.session_id:
            token_data |= self._export_session_id()

        await self._cache_saver(self._client_id, token_data)
