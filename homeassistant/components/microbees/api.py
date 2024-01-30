"""API for microBees bound to Home Assistant OAuth."""

from collections.abc import Iterable
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .auth import MicroBeesAuth
from .const import ACCESS_TOKEN

_LOGGER = logging.getLogger(__name__)


class ConfigEntryAuth(MicroBeesAuth):
    """Provide microBees authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize microBees Auth."""
        self.hass = hass
        self.session = oauth_session
        super().__init__(token=self.session.token[ACCESS_TOKEN])

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()

        return self._oauth_session.token[ACCESS_TOKEN]


def get_api_scopes(auth_implementation: str) -> Iterable[str]:
    """Return the microBees API scopes based on the auth implementation."""
    return ["read", "write"]
