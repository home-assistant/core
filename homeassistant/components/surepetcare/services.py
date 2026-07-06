"""Support for Sure Petcare services."""

from surepy.enums import Location
import voluptuous as vol

from homeassistant.const import ATTR_LOCATION
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, service

from .const import (
    ATTR_FLAP_ID,
    ATTR_LOCK_STATE,
    ATTR_PET_NAME,
    DOMAIN,
    SERVICE_SET_LOCK_STATE,
    SERVICE_SET_PET_LOCATION,
)
from .coordinator import SurePetcareConfigEntry


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register Sure Petcare services."""

    async def handle_set_lock_state(call: ServiceCall) -> None:
        """Set lock state for a flap."""
        entry: SurePetcareConfigEntry = service.async_get_config_entry(
            hass, DOMAIN, None
        )
        coordinator = entry.runtime_data
        flap_id = call.data[ATTR_FLAP_ID]
        if flap_id not in coordinator.data:
            raise ServiceValidationError(f"Unknown Sure Petcare flap ID: {flap_id}")
        await coordinator.handle_set_lock_state(call)

    async def handle_set_pet_location(call: ServiceCall) -> None:
        """Set pet location."""
        entry: SurePetcareConfigEntry = service.async_get_config_entry(
            hass, DOMAIN, None
        )
        coordinator = entry.runtime_data
        pet_name = call.data[ATTR_PET_NAME]
        if pet_name not in coordinator.get_pets():
            raise ServiceValidationError(f"Unknown Sure Petcare pet: {pet_name}")
        await coordinator.handle_set_pet_location(call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_LOCK_STATE,
        handle_set_lock_state,
        schema=vol.Schema(
            {
                vol.Required(ATTR_FLAP_ID): cv.positive_int,
                vol.Required(ATTR_LOCK_STATE): vol.All(
                    cv.string,
                    vol.Lower,
                    vol.In(
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
        SERVICE_SET_PET_LOCATION,
        handle_set_pet_location,
        schema=vol.Schema(
            {
                vol.Required(ATTR_PET_NAME): cv.string,
                vol.Required(ATTR_LOCATION): vol.In(
                    [
                        Location.INSIDE.name.title(),
                        Location.OUTSIDE.name.title(),
                    ]
                ),
            }
        ),
    )
