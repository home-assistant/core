"""The surepetcare integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from surepy.enums import Location
from surepy.exceptions import SurePetcareAuthenticationError, SurePetcareError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_FLAP_ID,
    ATTR_LOCATION,
    ATTR_LOCK_STATE,
    ATTR_PET_NAME,
    DOMAIN,
    SERVICE_SET_LOCK_STATE,
    SERVICE_SET_PET_LOCATION,
)
from .coordinator import SurePetcareDataCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.LOCK, Platform.SENSOR]
SCAN_INTERVAL = timedelta(minutes=3)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sure Petcare from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    try:
        hass.data[DOMAIN][entry.entry_id] = coordinator = SurePetcareDataCoordinator(
            hass,
            entry,
        )
    except SurePetcareAuthenticationError as error:
        _LOGGER.error("Unable to connect to surepetcare.io: Wrong credentials!")
        raise ConfigEntryAuthFailed from error
    except SurePetcareError as error:
        raise ConfigEntryNotReady from error

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    lock_state_service_schema = vol.Schema(
        {
            vol.Required(ATTR_FLAP_ID): vol.All(
                cv.positive_int, vol.In(coordinator.data.keys())
            ),
            vol.Required(ATTR_LOCK_STATE): vol.All(
                cv.string,
                vol.Lower,
                vol.In(coordinator.lock_states_callbacks.keys()),
            ),
        }
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_LOCK_STATE,
        coordinator.handle_set_lock_state,
        schema=lock_state_service_schema,
    )

    set_pet_location_schema = vol.Schema(
        {
            vol.Required(ATTR_PET_NAME): vol.In(coordinator.get_pets().keys()),
            vol.Required(ATTR_LOCATION): vol.In(
                [
                    Location.INSIDE.name.title(),
                    Location.OUTSIDE.name.title(),
                ]
            ),
        }
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_PET_LOCATION,
        coordinator.handle_set_pet_location,
        schema=set_pet_location_schema,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
