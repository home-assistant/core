"""Intents for the media_player integration."""
from __future__ import annotations

from homeassistant.const import SERVICE_VOLUME_DOWN, SERVICE_VOLUME_UP
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from . import DOMAIN

INTENT_VOLUME_UP = "HassVolumeUp"
INTENT_VOLUME_DOWN = "HassVolumeDown"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the media_player intents."""
    intent.async_register(
        hass, intent.ServiceIntentHandler(INTENT_VOLUME_UP, DOMAIN, SERVICE_VOLUME_UP)
    )
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(INTENT_VOLUME_DOWN, DOMAIN, SERVICE_VOLUME_DOWN),
    )
