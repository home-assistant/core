"""HA-side authentication adapter for the aioabrp library.

The library drives a long-lived telemetry stream from a background task and
asks for a fresh access token via :class:`aioabrp.AbstractAuth`. Its contract
is failure-containment: a raised :class:`aioabrp.AbrpAuthError` is treated as a
*terminal* auth failure (the library stops the stream and fires
``AUTH_FAILED``), while any other exception is treated as *transient* (the
library backs off and retries).

:class:`AbetterrouteplannerAuth` wraps HA's ``OAuth2Session`` and maps the
OAuth-refresh failure shapes onto that contract: a refresh
:class:`aiohttp.ClientResponseError` in the 4xx range — a revoked or rotated
refresh token — becomes terminal ``AbrpAuthError``; everything else (5xx,
generic ``ClientError``, timeouts) propagates unchanged so the library retries.

Deliberately, this does NOT raise ``ConfigEntryAuthFailed`` — that exception is
inert inside the library's background task. The setup-time garage fetch
(:func:`.coordinator.async_fetch_garage`) is the site that surfaces auth
failure to HA as ``ConfigEntryAuthFailed``.
"""

from http import HTTPStatus
from typing import cast, override

from aioabrp import AbrpAuthError, AbstractAuth
from aiohttp import ClientResponseError

from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session


class AbetterrouteplannerAuth(AbstractAuth):
    """Provide aioabrp with a fresh token from an HA ``OAuth2Session``."""

    def __init__(self, oauth_session: OAuth2Session) -> None:
        """Initialize the auth adapter with an OAuth2 session."""
        self._oauth_session = oauth_session

    @override
    async def async_get_access_token(self) -> str:
        """Return a valid access token, refreshing it if needed.

        A refresh ``ClientResponseError`` in the 4xx range (revoked/rotated
        refresh token) is terminal and surfaces as ``AbrpAuthError``. Any other
        failure propagates unchanged so the library treats it as transient.
        """
        try:
            await self._oauth_session.async_ensure_token_valid()
        except ClientResponseError as err:
            if HTTPStatus.BAD_REQUEST <= err.status < HTTPStatus.INTERNAL_SERVER_ERROR:
                raise AbrpAuthError from err
            raise
        return cast(str, self._oauth_session.token["access_token"])
