"""Services for the Subaru integration."""

from enum import StrEnum

import probatio

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service

from .const import DOMAIN, UNLOCK_VALID_DOORS


class SubaruService(StrEnum):
    """Store keys for Subaru services."""

    UNLOCK_SPECIFIC_DOOR = "unlock_specific_door"


class SubaruServiceArgument(StrEnum):
    """Store keys for Subaru service arguments."""

    DOOR = "door"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Subaru services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SubaruService.UNLOCK_SPECIFIC_DOOR,
        entity_domain=LOCK_DOMAIN,
        schema={
            probatio.Required(SubaruServiceArgument.DOOR): probatio.In(
                UNLOCK_VALID_DOORS
            )
        },
        func="async_unlock_specific_door",
    )
