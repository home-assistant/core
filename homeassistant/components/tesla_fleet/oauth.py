"""Provide oauth implementations for the Tesla Fleet integration."""

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from tesla_fleet_api.exceptions import OAuthExpired

from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session

from .const import AUTHORIZE_URL, SCOPES, TOKEN_URL

_T = TypeVar("_T")


class TeslaUserImplementation(AuthImplementation):
    """Tesla Fleet API user Oauth2 implementation."""

    def __init__(
        self, hass: HomeAssistant, auth_domain: str, credential: ClientCredential
    ) -> None:
        """Initialize user Oauth2 implementation."""

        super().__init__(
            hass,
            auth_domain,
            credential,
            AuthorizationServer(AUTHORIZE_URL, TOKEN_URL),
        )

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"prompt": "login", "scope": " ".join(SCOPES)}


class TeslaFleetOAuth2Session(OAuth2Session):
    """OAuth2 session with support for forcing a token refresh."""

    async def force_refresh_token(self) -> None:
        """Force a token refresh."""
        async with self._token_lock:
            new_token = await self.implementation.async_refresh_token(self.token)

            self.hass.config_entries.async_update_entry(
                self.config_entry, data={**self.config_entry.data, "token": new_token}
            )


async def async_retry_on_oauth_expired(
    api_call: Callable[[], Awaitable[_T]],
    oauth_session: TeslaFleetOAuth2Session,
) -> _T:
    """Retry an API request once after forcing a token refresh."""
    try:
        return await api_call()
    except OAuthExpired:
        await oauth_session.force_refresh_token()
        return await api_call()
