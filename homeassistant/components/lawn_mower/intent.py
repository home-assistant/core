"""Intents for the lawn mower integration."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from . import DOMAIN, SERVICE_DOCK, SERVICE_START_MOWING, LawnMowerEntityFeature

INTENT_LANW_MOWER_START_MOWING = "HassLawnMowerStartMowing"
INTENT_LANW_MOWER_DOCK = "HassLawnMowerDock"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the lawn mower intents."""
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_LANW_MOWER_START_MOWING,
            DOMAIN,
            SERVICE_START_MOWING,
            description="Starts a lawn mower",
            required_domains={DOMAIN},
            platforms={DOMAIN},
            required_features=LawnMowerEntityFeature.START_MOWING,
        ),
    )
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            INTENT_LANW_MOWER_DOCK,
            DOMAIN,
            SERVICE_DOCK,
            description="Sends a lawn mower to dock",
            required_domains={DOMAIN},
            platforms={DOMAIN},
            required_features=LawnMowerEntityFeature.DOCK,
        ),
    )
