"""Services for the Foursquare integration."""

from enum import StrEnum
from http import HTTPStatus
import logging

import probatio
import requests

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DATA_ACCESS_TOKEN, DOMAIN, EVENT_CHECKIN

_LOGGER = logging.getLogger(__name__)


class FoursquareService(StrEnum):
    """Store keys for Foursquare services."""

    CHECKIN = "checkin"


class FoursquareServiceArgument(StrEnum):
    """Store keys for Foursquare service arguments."""

    ALT = "alt"
    ALT_ACC = "altAcc"
    BROADCAST = "broadcast"
    EVENT_ID = "eventId"
    LL = "ll"
    LL_ACC = "llAcc"
    MENTIONS = "mentions"
    SHOUT = "shout"
    VENUE_ID = "venueId"


CHECKIN_SERVICE_SCHEMA = probatio.Schema(
    {
        probatio.Optional(FoursquareServiceArgument.ALT): cv.string,
        probatio.Optional(FoursquareServiceArgument.ALT_ACC): cv.string,
        probatio.Optional(FoursquareServiceArgument.BROADCAST): cv.string,
        probatio.Optional(FoursquareServiceArgument.EVENT_ID): cv.string,
        probatio.Optional(FoursquareServiceArgument.LL): cv.string,
        probatio.Optional(FoursquareServiceArgument.LL_ACC): cv.string,
        probatio.Optional(FoursquareServiceArgument.MENTIONS): cv.string,
        probatio.Optional(FoursquareServiceArgument.SHOUT): cv.string,
        probatio.Required(FoursquareServiceArgument.VENUE_ID): cv.string,
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
        DOMAIN, FoursquareService.CHECKIN, _checkin_user, schema=CHECKIN_SERVICE_SCHEMA
    )
