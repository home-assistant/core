"""Intents for the cover integration."""
from homeassistant.const import (
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from . import DOMAIN

INTENT_OPEN_COVER = "HassOpenCover"
INTENT_CLOSE_COVER = "HassCloseCover"
INTENT_STOP_COVER = "HassStopCover"
INTENT_SET_COVER_POSITION = "HassSetCoverPosition"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the cover intents."""
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_OPEN_COVER, DOMAIN, SERVICE_OPEN_COVER, "Opened {}"
        ),
    )
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_CLOSE_COVER, DOMAIN, SERVICE_CLOSE_COVER, "Closed {}"
        ),
    )
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_STOP_COVER, DOMAIN, SERVICE_STOP_COVER, "Stopped {}"
        ),
    )
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_SET_COVER_POSITION,
            DOMAIN,
            SERVICE_SET_COVER_POSITION,
            "Positioned {}",
        ),
    )
