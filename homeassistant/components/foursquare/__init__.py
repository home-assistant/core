"""Support for the Foursquare (Swarm) API."""

from http import HTTPStatus
import logging

from aiohttp import web
import probatio

from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_PUSH_SECRET, DATA_ACCESS_TOKEN, DOMAIN, EVENT_PUSH
from .services import setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.Schema(
            {
                probatio.Required(probatio.Secret(CONF_ACCESS_TOKEN)): cv.string,
                probatio.Required(probatio.Secret(CONF_PUSH_SECRET)): cv.string,
            }
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Foursquare component."""
    config = config[DOMAIN]
    hass.data[DATA_ACCESS_TOKEN] = config[CONF_ACCESS_TOKEN]
    setup_services(hass)

    hass.http.register_view(FoursquarePushReceiver(config[CONF_PUSH_SECRET]))

    return True


class FoursquarePushReceiver(HomeAssistantView):
    """Handle pushes from the Foursquare API."""

    requires_auth = False
    url = "/api/foursquare"
    name = "foursquare"

    def __init__(self, push_secret: str) -> None:
        """Initialize the OAuth callback view."""
        self.push_secret = push_secret

    async def post(self, request: web.Request) -> web.Response | None:
        """Accept the POST from Foursquare."""
        try:
            data = await request.json()
        except ValueError:
            return self.json_message("Invalid JSON", HTTPStatus.BAD_REQUEST)

        secret = data.pop("secret", None)

        _LOGGER.debug("Received Foursquare push: %s", data)

        if self.push_secret != secret:
            _LOGGER.error("Received Foursquare push with an invalid push secret")
            return self.json_message("Incorrect secret", HTTPStatus.BAD_REQUEST)

        request.app[KEY_HASS].bus.async_fire(EVENT_PUSH, data)
        return None
