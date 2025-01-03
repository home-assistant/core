"""API for OneDrive bound to Home Assistant OAuth."""

from typing import Any

from kiota_abstractions.authentication import (
    AccessTokenProvider,
    AllowedHostsValidator,
    BaseBearerTokenAuthenticationProvider,
)

from homeassistant.helpers import config_entry_oauth2_flow


class OneDriveConfigEntryAccessTokenProvider(AccessTokenProvider):
    """Provide OneDrive authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize OneDrive auth."""
        super().__init__()
        self._oauth_session = oauth_session

    async def get_authorization_token(  # pylint: disable=dangerous-default-value
        self,
        uri: str,
        additional_authentication_context: dict[str, Any] = {},
    ) -> str:
        """Return a valid authorization token."""
        await self._oauth_session.async_ensure_token_valid()
        return self._oauth_session.token["access_token"]

    def get_allowed_hosts_validator(self) -> AllowedHostsValidator:
        """Retrieve the allowed hosts validator."""
        # TODO: Implement this method


class OneDriveBearerTokenAuthenticationProvider(BaseBearerTokenAuthenticationProvider):
    """Provide OneDrive authentication tied to an OAuth2 based config entry."""
