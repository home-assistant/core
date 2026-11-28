"""Services for the Foursquare integration."""

from http import HTTPStatus
import logging

import probatio
import requests

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DATA_ACCESS_TOKEN, DOMAIN, EVENT_CHECKIN

_LOGGER = logging.getLogger(__name__)

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


def _checkin_user(call: ServiceCall) -> None:
    """Check a user in on Swarm."""
    hass = call.hass
    url = f"https://api.foursquare.com/v2/checkins/add?oauth_token={hass.data[DATA_ACCESS_TOKEN]}&v=20160802&m=swarm"
    response = requests.post(url, data=call.data, timeout=10)

    if response.status_code not in (HTTPStatus.OK, HTTPStatus.CREATED):
        _LOGGER.exception(
            "Error checking in user. Response %d: %s:",
            response.status_code,
            response.reason,
        )

    hass.bus.fire(EVENT_CHECKIN, {"text": response.text})


def setup_services(hass: HomeAssistant) -> None:
    """Register the Foursquare services."""
    hass.services.register(
        DOMAIN, "checkin", _checkin_user, schema=CHECKIN_SERVICE_SCHEMA
    )
