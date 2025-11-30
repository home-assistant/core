"""API for xbox bound to Home Assistant OAuth."""

from http import HTTPStatus

from aiohttp.client_exceptions import ClientResponseError
from httpx import AsyncClient
from pythonxbox.authentication.manager import AuthenticationManager
from pythonxbox.authentication.models import OAuth2TokenResponse

from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
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
            except ClientResponseError as e:
                if (
                    HTTPStatus.BAD_REQUEST
                    <= e.status
                    < HTTPStatus.INTERNAL_SERVER_ERROR
                ):
                    raise ConfigEntryAuthFailed(
                        translation_domain=DOMAIN,
                        translation_key="auth_exception",
                    ) from e
                raise ConfigEntryNotReady(
                    translation_domain=DOMAIN,
                    translation_key="request_exception",
                ) from e
            self.oauth = self._get_oauth_token()

        # This will skip the OAuth refresh and only refresh User and XSTS tokens
        await super().refresh_tokens()

    def _get_oauth_token(self) -> OAuth2TokenResponse:
        tokens = {**self._oauth_session.token}
        issued = tokens["expires_at"] - tokens["expires_in"]
        del tokens["expires_at"]
        token_response = OAuth2TokenResponse.model_validate(tokens)
        token_response.issued = utc_from_timestamp(issued)
        return token_response
