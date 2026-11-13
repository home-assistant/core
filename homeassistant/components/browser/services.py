"""Services for the browser integration."""

from enum import StrEnum
import webbrowser

import probatio

from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN

DEFAULT_URL = "https://www.google.com"


class BrowserService(StrEnum):
    """Store keys for Browser services."""

    BROWSE_URL = "browse_url"


class BrowserServiceArgument(StrEnum):
    """Store keys for Browser service arguments."""

    URL = "url"


SERVICE_BROWSE_URL_SCHEMA = probatio.Schema(
    {
        probatio.Required(
            BrowserServiceArgument.URL, default=DEFAULT_URL
        ): probatio.Url(),
    }
)


def _browser_url(service: ServiceCall) -> None:
    """Browse to URL."""
    webbrowser.open(service.data[BrowserServiceArgument.URL])


def setup_services(hass: HomeAssistant) -> None:
    """Register the browser services."""
    hass.services.register(
        DOMAIN,
        BrowserService.BROWSE_URL,
        _browser_url,
        schema=SERVICE_BROWSE_URL_SCHEMA,
    )
