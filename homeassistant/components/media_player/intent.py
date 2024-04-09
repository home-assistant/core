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

from . import ATTR_MEDIA_VOLUME_LEVEL, DOMAIN
from .const import MediaPlayerEntityFeature, MediaPlayerState

INTENT_MEDIA_PAUSE = "HassMediaPause"
INTENT_MEDIA_UNPAUSE = "HassMediaUnpause"
INTENT_MEDIA_NEXT = "HassMediaNext"
INTENT_SET_VOLUME = "HassSetVolume"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the media_player intents."""
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_MEDIA_UNPAUSE,
            DOMAIN,
            SERVICE_MEDIA_PLAY,
            required_domains={DOMAIN},
            required_states={MediaPlayerState.PAUSED},
        ),
    )
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_MEDIA_PAUSE,
            DOMAIN,
            SERVICE_MEDIA_PAUSE,
            required_domains={DOMAIN},
            required_features=MediaPlayerEntityFeature.PAUSE,
            required_states={MediaPlayerState.PLAYING},
        ),
    )
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_MEDIA_NEXT,
            DOMAIN,
            SERVICE_MEDIA_NEXT_TRACK,
            required_domains={DOMAIN},
            required_features=MediaPlayerEntityFeature.NEXT_TRACK,
            required_states={MediaPlayerState.PLAYING},
        ),
    )
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_SET_VOLUME,
            DOMAIN,
            SERVICE_VOLUME_SET,
            required_domains={DOMAIN},
            required_features=MediaPlayerEntityFeature.VOLUME_SET,
            required_states={MediaPlayerState.PLAYING},
            extra_slots={
                ATTR_MEDIA_VOLUME_LEVEL: vol.All(
                    vol.Range(min=0, max=100), lambda val: val / 100
                )
            },
        ),
    )
