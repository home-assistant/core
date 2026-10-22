"""Services for the Text-to-speech integration."""

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import (
    DATA_COMPONENT,
    DATA_TTS_MANAGER,
    DEFAULT_CACHE,
    DOMAIN,
    TextToSpeechService,
    TextToSpeechServiceArgument,
)

SCHEMA_SERVICE_CLEAR_CACHE = probatio.Schema({})


async def _async_clear_cache_handle(service: ServiceCall) -> None:
    """Handle clear cache service call."""
    await service.hass.data[DATA_TTS_MANAGER].async_clear_cache()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Text-to-speech services."""
    hass.data[DATA_COMPONENT].async_register_entity_service(
        TextToSpeechService.SPEAK,
        {
            probatio.Required(
                TextToSpeechServiceArgument.MEDIA_PLAYER_ENTITY_ID
            ): cv.comp_entity_ids,
            probatio.Required(TextToSpeechServiceArgument.MESSAGE): cv.string,
            probatio.Optional(
                TextToSpeechServiceArgument.CACHE, default=DEFAULT_CACHE
            ): cv.boolean,
            probatio.Optional(TextToSpeechServiceArgument.LANGUAGE): cv.string,
            probatio.Optional(TextToSpeechServiceArgument.OPTIONS): dict,
        },
        "async_speak",
    )

    hass.services.async_register(
        DOMAIN,
        TextToSpeechService.CLEAR_CACHE,
        _async_clear_cache_handle,
        schema=SCHEMA_SERVICE_CLEAR_CACHE,
    )
