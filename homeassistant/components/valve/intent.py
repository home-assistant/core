"""Intents for the valve integration."""

import voluptuous as vol

from homeassistant.const import SERVICE_SET_VALVE_POSITION
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from . import DOMAIN


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the valve intents."""
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            intent.INTENT_SET_POSITION,
            DOMAIN,
            SERVICE_SET_VALVE_POSITION,
            extra_slot_names={"position"},
            extra_slot_schema={
                vol.Required("position"): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=100)
                )
            },
        ),
    )
