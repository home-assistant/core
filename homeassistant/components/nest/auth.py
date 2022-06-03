"""OAuth implementations."""

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .const import (
    INSTALLED_AUTH_DOMAIN,
    OAUTH2_TOKEN,
    OOB_REDIRECT_URI,
    WEB_AUTH_DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class WebAuth(config_entry_oauth2_flow.LocalOAuth2Implementation):
    """OAuth implementation using OAuth for web applications."""

    name = "OAuth for Web"

    def __init__(
        self,
        hass: HomeAssistant,
        client_id: str,
        client_secret: str,
    ) -> None:
        """Initialize WebAuth."""
        super().__init__(
            hass,
            WEB_AUTH_DOMAIN,
            client_id,
            client_secret,
            "",  # Set during config flow
            OAUTH2_TOKEN,
        )


class InstalledAppAuth(config_entry_oauth2_flow.LocalOAuth2Implementation):
    """OAuth implementation using OAuth for installed applications."""

    name = "OAuth for Apps"

    def __init__(
        self,
        hass: HomeAssistant,
        client_id: str,
        client_secret: str,
    ) -> None:
        """Initialize InstalledAppAuth."""
        super().__init__(
            hass,
            INSTALLED_AUTH_DOMAIN,
            client_id,
            client_secret,
            "",  # Set during config flow
            OAUTH2_TOKEN,
        )

    @property
    def redirect_uri(self) -> str:
        """Return the redirect uri."""
        return OOB_REDIRECT_URI
