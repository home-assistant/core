"""HA-side authentication adapter for the aioabrp library.

The library treats ``AbrpAuthError`` as terminal (it stops the stream and fires
``AUTH_FAILED``) and every other exception as transient (it backs off and
retries), so only the OAuth2 helper's own terminal verdict —
``OAuth2TokenRequestReauthError`` — maps to ``AbrpAuthError``. Everything else,
including the helper's transient errors, propagates unchanged so the library's
backoff gets its chance. ``ConfigEntryAuthFailed`` is deliberately not raised
here: it is inert inside the library's background task, so the setup-time
garage fetch in ``coordinator.async_fetch_garage`` is where HA learns about
auth failure.
"""

from typing import cast, override

from aioabrp import AbrpAuthError, AbstractAuth

from homeassistant.exceptions import OAuth2TokenRequestReauthError
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session


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
        except OAuth2TokenRequestReauthError as err:
            raise AbrpAuthError from err
        return cast(str, self._oauth_session.token["access_token"])
