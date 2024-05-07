"""API for Ondilo ICO bound to Home Assistant OAuth."""

from asyncio import run_coroutine_threadsafe
import logging

from ondilo import Ondilo

from homeassistant import core
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers import config_entry_oauth2_flow

_LOGGER = logging.getLogger(__name__)


class OndiloClient(Ondilo):
    """Provide Ondilo ICO authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        hass: core.HomeAssistant,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize Ondilo ICO Auth."""
        self.hass = hass
        self.session = oauth_session
        super().__init__(self.session.token)

    def refresh_tokens(self) -> dict:
        """Refresh and return new Ondilo ICO tokens using Home Assistant OAuth2 session."""
        run_coroutine_threadsafe(
            self.session.async_ensure_token_valid(), self.hass.loop
        ).result()

        return self.session.token[CONF_ACCESS_TOKEN]
