"""API for xbox bound to Home Assistant OAuth."""

from aiohttp import ClientError
from httpx import AsyncClient, HTTPStatusError, RequestError
from pythonxbox.authentication.manager import AuthenticationManager
from pythonxbox.authentication.models import OAuth2TokenResponse
from pythonxbox.common.exceptions import AuthenticationException

from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.util.dt import utc_from_timestamp

from .const import DOMAIN


class AsyncConfigEntryAuth(AuthenticationManager):
    """Provide xbox authentication tied to an OAuth2 based config entry."""

    def __init__(self, session: AsyncClient, oauth_session: OAuth2Session) -> None:
        """Initialize xbox auth."""
        # Leaving out client credentials as they are handled by Home Assistant
        super().__init__(session, "", "", "")
        self._oauth_session = oauth_session
        self.oauth = self._get_oauth_token()

    async def refresh_tokens(self) -> None:
        """Return a valid access token."""

        if not self._oauth_session.valid_token:
            try:
                await self._oauth_session.async_ensure_token_valid()
            except OAuth2TokenRequestReauthError as e:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="auth_exception",
                ) from e
            except (OAuth2TokenRequestTransientError, ClientError) as e:
                raise ConfigEntryNotReady(
                    translation_domain=DOMAIN,
                    translation_key="request_exception",
                ) from e
            self.oauth = self._get_oauth_token()

        # This will skip the OAuth refresh and only refresh User and XSTS tokens
        try:
            await super().refresh_tokens()
        except AuthenticationException as e:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_exception",
            ) from e
        except (RequestError, HTTPStatusError) as e:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="request_exception",
            ) from e

    def _get_oauth_token(self) -> OAuth2TokenResponse:
        tokens = {**self._oauth_session.token}
        issued = tokens["expires_at"] - tokens["expires_in"]
        del tokens["expires_at"]
        token_response = OAuth2TokenResponse.model_validate(tokens)
        token_response.issued = utc_from_timestamp(issued)
        return token_response
