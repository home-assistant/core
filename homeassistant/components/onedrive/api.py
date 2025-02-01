"""API for OneDrive bound to Home Assistant OAuth."""

from typing import Any, cast

from kiota_abstractions.authentication import AccessTokenProvider, AllowedHostsValidator

from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers import config_entry_oauth2_flow


class OneDriveAccessTokenProvider(AccessTokenProvider):
    """Provide OneDrive authentication tied to an OAuth2 based config entry."""

    def __init__(self) -> None:
        """Initialize OneDrive auth."""
        super().__init__()
        # currently allowing all hosts
        self._allowed_hosts_validator = AllowedHostsValidator(allowed_hosts=[])

    def get_allowed_hosts_validator(self) -> AllowedHostsValidator:
        """Retrieve the allowed hosts validator."""
        return self._allowed_hosts_validator


class OneDriveConfigFlowAccessTokenProvider(OneDriveAccessTokenProvider):
    """Provide OneDrive authentication tied to an OAuth2 based config entry."""

    def __init__(self, token: str) -> None:
        """Initialize OneDrive auth."""
        super().__init__()
        self._token = token

    async def get_authorization_token(  # pylint: disable=dangerous-default-value
        self, uri: str, additional_authentication_context: dict[str, Any] = {}
    ) -> str:
        """Return a valid authorization token."""
        return self._token


class OneDriveConfigEntryAccessTokenProvider(OneDriveAccessTokenProvider):
    """Provide OneDrive authentication tied to an OAuth2 based config entry."""

    def __init__(self, oauth_session: config_entry_oauth2_flow.OAuth2Session) -> None:
        """Initialize OneDrive auth."""
        super().__init__()
        self._oauth_session = oauth_session

    async def get_authorization_token(  # pylint: disable=dangerous-default-value
        self, uri: str, additional_authentication_context: dict[str, Any] = {}
    ) -> str:
        """Return a valid authorization token."""
        await self._oauth_session.async_ensure_token_valid()
        return cast(str, self._oauth_session.token[CONF_ACCESS_TOKEN])
