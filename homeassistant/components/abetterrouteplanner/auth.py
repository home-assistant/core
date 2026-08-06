"""HA-side authentication adapter for the aioabrp library.

The library treats ``AbrpAuthError`` as terminal (it stops the stream and fires
``AUTH_FAILED``) and every other exception as transient (it backs off and
retries), so only a credential-related refresh failure — a revoked or rotated
refresh token — maps to ``AbrpAuthError``. Every other status, including the
retryable 4xx ones (429, 408), propagates unchanged so the library's backoff
gets its chance. ``ConfigEntryAuthFailed`` is deliberately not raised here: it
is inert inside the library's background task, so the setup-time garage fetch
in ``coordinator.async_fetch_garage`` is where HA learns about auth failure.
"""

from http import HTTPStatus
from typing import cast, override

from aioabrp import AbrpAuthError, AbstractAuth
from aiohttp import ClientResponseError

from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session

# RFC 6749 returns ``invalid_grant`` for a revoked/rotated token as a 400.
TERMINAL_REFRESH_STATUSES = frozenset(
    {HTTPStatus.BAD_REQUEST, HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}
)


class AbetterrouteplannerAuth(AbstractAuth):
    """Provide aioabrp with a fresh token from an HA ``OAuth2Session``."""

    def __init__(self, oauth_session: OAuth2Session) -> None:
        """Initialize the auth adapter with an OAuth2 session."""
        self._oauth_session = oauth_session

    @override
    async def async_get_access_token(self) -> str:
        """Return a valid access token, refreshing it if needed."""
        try:
            await self._oauth_session.async_ensure_token_valid()
        except ClientResponseError as err:
            if err.status in TERMINAL_REFRESH_STATUSES:
                raise AbrpAuthError from err
            raise
        return cast(str, self._oauth_session.token["access_token"])
