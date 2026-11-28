"""Services for the browser integration."""

import webbrowser

import probatio

from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN

ATTR_URL = "url"
ATTR_URL_DEFAULT = "https://www.google.com"

SERVICE_BROWSE_URL = "browse_url"

SERVICE_BROWSE_URL_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_URL, default=ATTR_URL_DEFAULT): probatio.Url(),
    }
)


def _browser_url(service: ServiceCall) -> None:
    """Browse to URL."""
    webbrowser.open(service.data[ATTR_URL])


def setup_services(hass: HomeAssistant) -> None:
    """Register the browser services."""
    hass.services.register(
        DOMAIN,
        SERVICE_BROWSE_URL,
        _browser_url,
        schema=SERVICE_BROWSE_URL_SCHEMA,
    )
