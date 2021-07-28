"""API for xbox bound to Home Assistant OAuth."""
from aiohttp import ClientSession
from xbox.webapi.authentication.manager import AuthenticationManager
from xbox.webapi.authentication.models import OAuth2TokenResponse

from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.util.dt import utc_from_timestamp


class AsyncConfigEntryAuth(AuthenticationManager):
    """Provide xbox authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize xbox auth."""
        # Leaving out client credentials as they are handled by Home Assistant
        super().__init__(websession, "", "", "")
        self._oauth_session = oauth_session
        self.oauth = self._get_oauth_token()

    async def refresh_tokens(self) -> None:
        """Return a valid access token."""
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()
            self.oauth = self._get_oauth_token()

        # This will skip the OAuth refresh and only refresh User and XSTS tokens
        await super().refresh_tokens()

    def _get_oauth_token(self) -> OAuth2TokenResponse:
        tokens = {**self._oauth_session.token}
        issued = tokens["expires_at"] - tokens["expires_in"]
        del tokens["expires_at"]
        token_response = OAuth2TokenResponse.parse_obj(tokens)
        token_response.issued = utc_from_timestamp(issued)
        return token_response
