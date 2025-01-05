"""API for Google Drive bound to Home Assistant OAuth."""

from __future__ import annotations

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientError, ClientResponseError
from google.auth.exceptions import RefreshError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DRIVE_API_FILES


def create_headers(access_token: str) -> dict[str, str]:
    """Create headers with the provided access token."""
    return {
        "Authorization": f"Bearer {access_token}",
    }


async def async_check_file_exists(
    session: ClientSession, headers: dict[str, str], file_id: str
) -> None:
    """Check the provided file or folder exists.

    :raises ClientError: if there is any error, including 404
    """
    resp = await session.get(
        f"{DRIVE_API_FILES}/{file_id}",
        params={"fields": ""},
        headers=headers,
    )
    resp.raise_for_status()


class AsyncConfigEntryAuth:
    """Provide Google Drive authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        oauth2_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize Google Drive Auth."""
        self._hass = hass
        self.oauth_session = oauth2_session

    @property
    def access_token(self) -> str:
        """Return the access token."""
        return str(self.oauth_session.token[CONF_ACCESS_TOKEN])

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
