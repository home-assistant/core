"""Support for the Foursquare (Swarm) API."""

from http import HTTPStatus
import logging

from aiohttp import web
import probatio
import requests

from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

CONF_PUSH_SECRET = "push_secret"

DOMAIN = "foursquare"

EVENT_CHECKIN = "foursquare.checkin"
EVENT_PUSH = "foursquare.push"

SERVICE_CHECKIN = "checkin"

CHECKIN_SERVICE_SCHEMA = probatio.Schema(
    {
        probatio.Optional("alt"): cv.string,
        probatio.Optional("altAcc"): cv.string,
        probatio.Optional("broadcast"): cv.string,
        probatio.Optional("eventId"): cv.string,
        probatio.Optional("ll"): cv.string,
        probatio.Optional("llAcc"): cv.string,
        probatio.Optional("mentions"): cv.string,
        probatio.Optional("shout"): cv.string,
        probatio.Required("venueId"): cv.string,
    }
)

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.Schema(
            {
                probatio.Required(CONF_ACCESS_TOKEN): cv.string,
                probatio.Required(CONF_PUSH_SECRET): cv.string,
            }
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Foursquare component."""
    config = config[DOMAIN]

    def checkin_user(call: ServiceCall) -> None:
        """Check a user in on Swarm."""
        url = f"https://api.foursquare.com/v2/checkins/add?oauth_token={config[CONF_ACCESS_TOKEN]}&v=20160802&m=swarm"
        response = requests.post(url, data=call.data, timeout=10)

        if response.status_code not in (HTTPStatus.OK, HTTPStatus.CREATED):
            _LOGGER.exception(
                "Error checking in user. Response %d: %s:",
                response.status_code,
                response.reason,
            )

        hass.bus.fire(EVENT_CHECKIN, {"text": response.text})

    # Register our service with Home Assistant.
    hass.services.register(
        DOMAIN, "checkin", checkin_user, schema=CHECKIN_SERVICE_SCHEMA
    )

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
