"""Intents for the cover integration."""

from homeassistant.const import SERVICE_CLOSE_COVER, SERVICE_OPEN_COVER
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from . import DOMAIN, INTENT_CLOSE_COVER, INTENT_OPEN_COVER, CoverDeviceClass


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the cover intents."""
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_OPEN_COVER,
            DOMAIN,
            SERVICE_OPEN_COVER,
            "Opening {}",
            description="Opens a cover",
            platforms={DOMAIN},
            device_classes={CoverDeviceClass},
        ),
    )
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_CLOSE_COVER,
            DOMAIN,
            SERVICE_CLOSE_COVER,
            "Closing {}",
            description="Closes a cover",
            platforms={DOMAIN},
            device_classes={CoverDeviceClass},
        ),
    )
