"""Intents for the client integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    MediaPlayerDeviceClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, intent

from . import DOMAIN
from .const import ATTR_MEDIA_ID, ATTR_RADIO_MODE, SERVICE_PLAY_MEDIA_ADVANCED

INTENT_PLAY_MEDIA_ASSIST = "MassPlayMediaAssist"
ARTIST_SLOT = "artist"
TRACK_SLOT = "track"
ALBUM_SLOT = "album"
RADIO_SLOT = "radio"
PLAYLIST_SLOT = "playlist"
RADIO_MODE_SLOT = "radio_mode"
SLOT_VALUE = "value"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the Music Assistant intents."""
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_PLAY_MEDIA_ASSIST,
            DOMAIN,
            SERVICE_PLAY_MEDIA_ADVANCED,
            description="Handle Assist Play Media intents.",
            optional_slots={
                (ARTIST_SLOT, ATTR_MEDIA_ID): cv.string,
                (TRACK_SLOT, ATTR_MEDIA_ID): cv.string,
                (ALBUM_SLOT, ATTR_MEDIA_ID): cv.string,
                (RADIO_SLOT, ATTR_MEDIA_ID): cv.string,
                (PLAYLIST_SLOT, ATTR_MEDIA_ID): cv.string,
                (RADIO_MODE_SLOT, ATTR_RADIO_MODE): vol.Coerce(bool),
            },
            required_domains={MEDIA_PLAYER_DOMAIN},
            platforms={MEDIA_PLAYER_DOMAIN},
            device_classes={MediaPlayerDeviceClass},
        ),
    )
