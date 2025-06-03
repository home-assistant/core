"""Support for launching a web browser on the host machine."""

import webbrowser

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

ATTR_URL = "url"
ATTR_URL_DEFAULT = "https://www.google.com"

DOMAIN = "browser"

SERVICE_BROWSE_URL = "browse_url"

SERVICE_BROWSE_URL_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_URL, default=ATTR_URL_DEFAULT): vol.Url(),
    }
)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


def _browser_url(service: ServiceCall) -> None:
    """Browse to URL."""
    webbrowser.open(service.data[ATTR_URL])


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Listen for browse_url events."""

    hass.services.register(
        DOMAIN,
        SERVICE_BROWSE_URL,
        _browser_url,
        schema=SERVICE_BROWSE_URL_SCHEMA,
    )

    return True
