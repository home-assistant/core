"""Intents for the valve integration."""
from homeassistant.const import SERVICE_CLOSE_VALVE, SERVICE_OPEN_VALVE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from . import DOMAIN

INTENT_OPEN_VALVE = "HassOpenValve"
INTENT_CLOSE_VALVE = "HassCloseValve"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the valve intents."""
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_OPEN_VALVE, DOMAIN, SERVICE_OPEN_VALVE, "Opened {}"
        ),
    )
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_CLOSE_VALVE, DOMAIN, SERVICE_CLOSE_VALVE, "Closed {}"
        ),
    )
