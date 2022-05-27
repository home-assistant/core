"""OAuth implementations."""
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .const import (
    INSTALLED_AUTH_DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
    OOB_REDIRECT_URI,
    WEB_AUTH_DOMAIN,
)


class WebAuth(config_entry_oauth2_flow.LocalOAuth2Implementation):
    """OAuth implementation using OAuth for web applications."""

    name = "OAuth for Web"

    def __init__(
        self, hass: HomeAssistant, client_id: str, client_secret: str, project_id: str
    ) -> None:
        """Initialize WebAuth."""
        super().__init__(
            hass,
            WEB_AUTH_DOMAIN,
            client_id,
            client_secret,
            OAUTH2_AUTHORIZE.format(project_id=project_id),
            OAUTH2_TOKEN,
        )


class InstalledAppAuth(config_entry_oauth2_flow.LocalOAuth2Implementation):
    """OAuth implementation using OAuth for installed applications."""

    name = "OAuth for Apps"

    def __init__(
        self, hass: HomeAssistant, client_id: str, client_secret: str, project_id: str
    ) -> None:
        """Initialize InstalledAppAuth."""
        super().__init__(
            hass,
            INSTALLED_AUTH_DOMAIN,
            client_id,
            client_secret,
            OAUTH2_AUTHORIZE.format(project_id=project_id),
            OAUTH2_TOKEN,
        )

    @property
    def redirect_uri(self) -> str:
        """Return the redirect uri."""
        return OOB_REDIRECT_URI
