"""API for Google Mail bound to Home Assistant OAuth."""
from aiohttp.client_exceptions import ClientError, ClientResponseError
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import config_entry_oauth2_flow


class AsyncConfigEntryAuth:
    """Provide Google Mail authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        oauth2_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize Google Mail Auth."""
        self.oauth_session = oauth2_session

    @property
    def access_token(self) -> str:
        """Return the access token."""
        return self.oauth_session.token[CONF_ACCESS_TOKEN]

    async def check_and_refresh_token(self) -> str:
        """Check the token."""
        try:
            await self.oauth_session.async_ensure_token_valid()
        except (RefreshError, ClientResponseError, ClientError) as ex:
            if (
                self.oauth_session.config_entry.state
                is ConfigEntryState.SETUP_IN_PROGRESS
            ):
                if isinstance(ex, ClientResponseError) and 400 <= ex.status < 500:
                    raise ConfigEntryAuthFailed(
                        "OAuth session is not valid, reauth required"
                    ) from ex
                raise ConfigEntryNotReady from ex
            if (
                isinstance(ex, RefreshError)
                or hasattr(ex, "status")
                and ex.status == 400
            ):
                self.oauth_session.config_entry.async_start_reauth(
                    self.oauth_session.hass
                )
            raise HomeAssistantError(ex) from ex
        return self.access_token

    async def get_resource(self) -> Resource:
        """Get current resource."""
        credentials = Credentials(await self.check_and_refresh_token())
        return build("gmail", "v1", credentials=credentials)
