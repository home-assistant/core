"""API for OneDrive bound to Home Assistant OAuth."""

from typing import cast

from onedrive_personal_sdk import TokenProvider

from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers import config_entry_oauth2_flow


class OneDriveConfigFlowAccessTokenProvider(TokenProvider):
    """Provide OneDrive authentication tied to an OAuth2 based config entry."""

    def __init__(self, token: str) -> None:
        """Initialize OneDrive auth."""
        super().__init__()
        self._token = token

    def async_get_access_token(self) -> str:
        """Return a valid access token."""
        return self._token


class OneDriveConfigEntryAccessTokenProvider(TokenProvider):
    """Provide OneDrive authentication tied to an OAuth2 based config entry."""

    def __init__(self, oauth_session: config_entry_oauth2_flow.OAuth2Session) -> None:
        """Initialize OneDrive auth."""
        super().__init__()
        self._oauth_session = oauth_session

    def async_get_access_token(self) -> str:
        """Return a valid access token."""
        return cast(str, self._oauth_session.token[CONF_ACCESS_TOKEN])
