"""Shark IQ services."""

from enum import StrEnum

import probatio

from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class SharkIqService(StrEnum):
    """Store keys for Shark IQ services."""

    CLEAN_ROOM = "clean_room"


class SharkIqServiceArgument(StrEnum):
    """Store keys for Shark IQ service arguments."""

    ROOMS = "rooms"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    # Vacuum Services
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SharkIqService.CLEAN_ROOM,
        entity_domain=VACUUM_DOMAIN,
        schema={
            probatio.Required(SharkIqServiceArgument.ROOMS): probatio.All(
                probatio.EnsureList(), probatio.NonEmpty(), [cv.string]
            ),
        },
        func="async_clean_room",
    )
