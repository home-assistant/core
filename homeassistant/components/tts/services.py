"""Services for the Text-to-speech integration."""

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_CACHE,
    ATTR_DAYS,
    ATTR_LANGUAGE,
    ATTR_MEDIA_PLAYER_ENTITY_ID,
    ATTR_MESSAGE,
    ATTR_OPTIONS,
    DATA_COMPONENT,
    DATA_TTS_MANAGER,
    DEFAULT_CACHE,
    DOMAIN,
    SERVICE_CLEAR_CACHE,
)

SCHEMA_SERVICE_CLEAR_CACHE = probatio.Schema(
    {
        probatio.Optional(ATTR_DAYS): probatio.All(
            probatio.Coerce(int), probatio.Range(min=1, max=3650)
        )
    }
)


async def _async_clear_cache_handle(service: ServiceCall) -> None:
    """Handle clear cache service call."""
    await service.hass.data[DATA_TTS_MANAGER].async_clear_cache(
        service.data.get(ATTR_DAYS)
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Text-to-speech services."""
    hass.data[DATA_COMPONENT].async_register_entity_service(
        "speak",
        {
            probatio.Required(ATTR_MEDIA_PLAYER_ENTITY_ID): cv.comp_entity_ids,
            probatio.Required(ATTR_MESSAGE): cv.string,
            probatio.Optional(ATTR_CACHE, default=DEFAULT_CACHE): cv.boolean,
            probatio.Optional(ATTR_LANGUAGE): cv.string,
            probatio.Optional(ATTR_OPTIONS): dict,
        },
        "async_speak",
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_CACHE,
        _async_clear_cache_handle,
        schema=SCHEMA_SERVICE_CLEAR_CACHE,
    )
