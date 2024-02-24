"""Intents for the valve integration."""

import voluptuous as vol

from homeassistant.const import SERVICE_SET_VALVE_POSITION
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from . import ATTR_POSITION, DOMAIN


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the valve intents."""
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            intent.INTENT_SET_POSITION,
            DOMAIN,
            SERVICE_SET_VALVE_POSITION,
            extra_slots={ATTR_POSITION: vol.All(vol.Range(min=0, max=100))},
        ),
    )
