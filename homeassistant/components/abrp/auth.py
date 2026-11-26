"""HA-side authentication adapter for the aioabrp library.

Only the OAuth2 helper's terminal verdict, ``OAuth2TokenRequestReauthError``,
maps to ``AbrpAuthError``, which the library treats as terminal. Other refresh
failures map to ``AbrpApiError``: REST calls then fail like any API error, and
the stream backs off and retries. ``ConfigEntryAuthFailed`` is deliberately not
raised here: it is inert inside the library's background task.
"""

from typing import cast, override

from aioabrp import AbrpApiError, AbrpAuthError, AbstractAuth

from homeassistant.exceptions import (
    OAuth2TokenRequestBaseError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session


class AbrpAuth(AbstractAuth):
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
        # The helper wraps HTTP and connection failures, but not a bare timeout.
        except (OAuth2TokenRequestBaseError, TimeoutError) as err:
            raise AbrpApiError(
                f"token refresh failed: {type(err).__name__}: {err}"
            ) from err
        return cast(str, self._oauth_session.token["access_token"])
