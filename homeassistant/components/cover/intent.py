"""Intents for the cover integration."""
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from . import DOMAIN, SERVICE_OPEN_COVER, SERVICE_CLOSE_COVER

INTENT_OPEN_COVER = "HassOpenCover"
INTENT_CLOSE_COVER = "HassCloseCover"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the cover intents."""
    hass.helpers.intent.async_register(
        intent.ServiceIntentHandler(
            INTENT_OPEN_COVER, DOMAIN, SERVICE_OPEN_COVER, "Opened {}"
        )
    )
    hass.helpers.intent.async_register(
        intent.ServiceIntentHandler(
            INTENT_CLOSE_COVER, DOMAIN, SERVICE_CLOSE_COVER, "Closed {}"
        )
    )
