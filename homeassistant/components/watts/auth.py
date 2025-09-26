"""Authentication for Watts Vision+ using OAuth2 config entry."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow


class ConfigEntryAuth:
    """Provide Watts Vision+ authentication with OAuth2 config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize Watts Vision+ Auth."""

        self.hass = hass
        self.session = oauth_session
        self.token = self.session.token

    async def refresh_tokens(self) -> str:
        """Refresh and return new Watts Vision+ tokens."""

        await self.session.async_ensure_token_valid()
        return self.session.token["access_token"]
