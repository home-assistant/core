"""Intents for the media_player integration."""

import voluptuous as vol

from homeassistant.const import (
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_VOLUME_SET,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
import homeassistant.helpers.config_validation as cv

from . import ATTR_MEDIA_VOLUME_LEVEL, DOMAIN

INTENT_MEDIA_PAUSE = "HassMediaPause"
INTENT_MEDIA_UNPAUSE = "HassMediaUnpause"
INTENT_MEDIA_NEXT = "HassMediaNext"
INTENT_SET_VOLUME = "HassSetVolume"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the media_player intents."""
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(INTENT_MEDIA_UNPAUSE, DOMAIN, SERVICE_MEDIA_PLAY),
    )
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(INTENT_MEDIA_PAUSE, DOMAIN, SERVICE_MEDIA_PAUSE),
    )
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_MEDIA_NEXT, DOMAIN, SERVICE_MEDIA_NEXT_TRACK
        ),
    )
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_SET_VOLUME,
            DOMAIN,
            SERVICE_VOLUME_SET,
            extra_slot_names={ATTR_MEDIA_VOLUME_LEVEL},
            extra_slot_schema={vol.Required(ATTR_MEDIA_VOLUME_LEVEL): cv.small_float},
        ),
    )
