"""Intents for the vacuum integration."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from . import DOMAIN, SERVICE_RETURN_TO_BASE, SERVICE_START

INTENT_VACUUM_START = "HassVacuumStart"
INTENT_VACUUM_RETURN_TO_BASE = "HassVacuumReturnToBase"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the vacuum intents."""
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(INTENT_VACUUM_START, DOMAIN, SERVICE_START),
    )
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_VACUUM_RETURN_TO_BASE, DOMAIN, SERVICE_RETURN_TO_BASE
        ),
    )
