"""Intents for the cover integration."""

import voluptuous as vol

from homeassistant.const import (
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from . import ATTR_POSITION, DOMAIN

INTENT_OPEN_COVER = "HassOpenCover"
INTENT_CLOSE_COVER = "HassCloseCover"


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
            intent.INTENT_SET_POSITION,
            DOMAIN,
            SERVICE_SET_COVER_POSITION,
            extra_slots={ATTR_POSITION: vol.All(vol.Range(min=0, max=100))},
        ),
    )
