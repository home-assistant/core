"""API helpers for the Eve Online integration."""

from __future__ import annotations

from typing import cast

from aiohttp import ClientError, ClientSession
from eveonline.auth import AbstractAuth

from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import UpdateFailed


class AsyncConfigEntryAuth(AbstractAuth):
    """Provide Eve Online authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: OAuth2Session,
    ) -> None:
        """Initialize Eve Online auth."""
        super().__init__(websession)
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        try:
            await self._oauth_session.async_ensure_token_valid()
        except OAuth2TokenRequestReauthError as err:
            raise ConfigEntryAuthFailed(
                "Authentication failed, please reauthenticate"
            ) from err
        except (OAuth2TokenRequestTransientError, ClientError) as err:
            raise UpdateFailed(f"Failed to refresh OAuth token: {err}") from err
        return cast(str, self._oauth_session.token["access_token"])
