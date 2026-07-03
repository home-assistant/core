"""The surepetcare integration."""

from datetime import timedelta
import logging

from surepy.enums import Location
from surepy.exceptions import SurePetcareAuthenticationError, SurePetcareError
import voluptuous as vol

from homeassistant.const import ATTR_LOCATION, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_FLAP_ID,
    ATTR_LOCK_STATE,
    ATTR_PET_NAME,
    DOMAIN,
    SERVICE_SET_LOCK_STATE,
    SERVICE_SET_PET_LOCATION,
)
from .coordinator import SurePetcareConfigEntry, SurePetcareDataCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.LOCK, Platform.SENSOR]
SCAN_INTERVAL = timedelta(minutes=3)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Sure Petcare services."""

    async def handle_set_lock_state(call: ServiceCall) -> None:
        """Set lock state for a flap."""
        flap_id = call.data[ATTR_FLAP_ID]
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            coordinator: SurePetcareDataCoordinator = entry.runtime_data
            if flap_id in coordinator.data:
                await coordinator.handle_set_lock_state(call)
                return
        raise HomeAssistantError(f"Unknown Sure Petcare flap ID: {flap_id}")

    async def handle_set_pet_location(call: ServiceCall) -> None:
        """Set pet location."""
        pet_name = call.data[ATTR_PET_NAME]
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            coordinator: SurePetcareDataCoordinator = entry.runtime_data
            if pet_name in coordinator.get_pets():
                await coordinator.handle_set_pet_location(call)
                return
        raise HomeAssistantError(f"Unknown Sure Petcare pet: {pet_name}")

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

    return True


async def async_setup_entry(hass: HomeAssistant, entry: SurePetcareConfigEntry) -> bool:
    """Set up Sure Petcare from a config entry."""
    try:
        coordinator = SurePetcareDataCoordinator(hass, entry)
    except SurePetcareAuthenticationError as error:
        _LOGGER.error("Unable to connect to surepetcare.io: Wrong credentials!")
        raise ConfigEntryAuthFailed from error
    except SurePetcareError as error:
        raise ConfigEntryNotReady from error

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SurePetcareConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
