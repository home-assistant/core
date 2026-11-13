"""Support for Sure Petcare services."""

from enum import StrEnum

import probatio
from surepy.enums import Location

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN
from .coordinator import SurePetcareConfigEntry


class SurePetcareService(StrEnum):
    """Store keys for Sure Petcare services."""

    SET_LOCK_STATE = "set_lock_state"
    SET_PET_LOCATION = "set_pet_location"


class SurePetcareServiceArgument(StrEnum):
    """Store keys for Sure Petcare service arguments."""

    FLAP_ID = "flap_id"
    LOCK_STATE = "lock_state"
    PET_NAME = "pet_name"
    LOCATION = "location"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register Sure Petcare services."""

    async def handle_set_lock_state(call: ServiceCall) -> None:
        """Set lock state for a flap."""
        entry: SurePetcareConfigEntry = service.async_get_config_entry(
            hass, DOMAIN, None
        )
        coordinator = entry.runtime_data
        if call.data[SurePetcareServiceArgument.FLAP_ID] not in coordinator.data:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_flap_id",
                translation_placeholders={
                    "flap_id": call.data[SurePetcareServiceArgument.FLAP_ID]
                },
            )
        await coordinator.handle_set_lock_state(
            call.data[SurePetcareServiceArgument.FLAP_ID],
            call.data[SurePetcareServiceArgument.LOCK_STATE],
        )

    async def handle_set_pet_location(call: ServiceCall) -> None:
        """Set pet location."""
        entry: SurePetcareConfigEntry = service.async_get_config_entry(
            hass, DOMAIN, None
        )
        coordinator = entry.runtime_data
        if call.data[SurePetcareServiceArgument.PET_NAME] not in coordinator.get_pets():
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_pet_name",
                translation_placeholders={
                    "pet_name": call.data[SurePetcareServiceArgument.PET_NAME]
                },
            )
        await coordinator.handle_set_pet_location(
            call.data[SurePetcareServiceArgument.PET_NAME],
            call.data[SurePetcareServiceArgument.LOCATION],
        )

    hass.services.async_register(
        DOMAIN,
        SurePetcareService.SET_LOCK_STATE,
        handle_set_lock_state,
        schema=probatio.Schema(
            {
                probatio.Required(SurePetcareServiceArgument.FLAP_ID): cv.positive_int,
                probatio.Required(SurePetcareServiceArgument.LOCK_STATE): probatio.All(
                    cv.string,
                    probatio.Lower,
                    probatio.In(
                        [
                            "unlocked",
                            "locked_in",
                            "locked_out",
                            "locked_all",
                        ]
                    ),
                ),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SurePetcareService.SET_PET_LOCATION,
        handle_set_pet_location,
        schema=probatio.Schema(
            {
                probatio.Required(SurePetcareServiceArgument.PET_NAME): cv.string,
                probatio.Required(SurePetcareServiceArgument.LOCATION): probatio.In(
                    [
                        Location.INSIDE.name.title(),
                        Location.OUTSIDE.name.title(),
                    ]
                ),
            }
        ),
    )
