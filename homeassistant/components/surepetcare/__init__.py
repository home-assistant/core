"""The surepetcare integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from surepy import Surepy, SurepyEntity
from surepy.enums import EntityType, Location, LockState
from surepy.exceptions import SurePetcareAuthenticationError, SurePetcareError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_FLAP_ID,
    ATTR_LOCATION,
    ATTR_LOCK_STATE,
    ATTR_PET_NAME,
    DOMAIN,
    SERVICE_SET_LOCK_STATE,
    SERVICE_SET_PET_LOCATION,
    SURE_API_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.LOCK, Platform.SENSOR]
SCAN_INTERVAL = timedelta(minutes=3)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sure Petcare from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    try:
        hass.data[DOMAIN][entry.entry_id] = coordinator = SurePetcareDataCoordinator(
            entry,
            hass,
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


class SurePetcareDataCoordinator(DataUpdateCoordinator[dict[int, SurepyEntity]]):  # pylint: disable=hass-enforce-coordinator-module
    """Handle Surepetcare data."""

    def __init__(self, entry: ConfigEntry, hass: HomeAssistant) -> None:
        """Initialize the data handler."""
        self.surepy = Surepy(
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            auth_token=entry.data[CONF_TOKEN],
            api_timeout=SURE_API_TIMEOUT,
            session=async_get_clientsession(hass),
        )
        self.lock_states_callbacks = {
            LockState.UNLOCKED.name.lower(): self.surepy.sac.unlock,
            LockState.LOCKED_IN.name.lower(): self.surepy.sac.lock_in,
            LockState.LOCKED_OUT.name.lower(): self.surepy.sac.lock_out,
            LockState.LOCKED_ALL.name.lower(): self.surepy.sac.lock,
        }
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[int, SurepyEntity]:
        """Get the latest data from Sure Petcare."""
        try:
            return await self.surepy.get_entities(refresh=True)
        except SurePetcareAuthenticationError as err:
            raise ConfigEntryAuthFailed("Invalid username/password") from err
        except SurePetcareError as err:
            raise UpdateFailed(f"Unable to fetch data: {err}") from err

    async def handle_set_lock_state(self, call: ServiceCall) -> None:
        """Call when setting the lock state."""
        flap_id = call.data[ATTR_FLAP_ID]
        state = call.data[ATTR_LOCK_STATE]
        await self.lock_states_callbacks[state](flap_id)
        await self.async_request_refresh()

    def get_pets(self) -> dict[str, int]:
        """Get pets."""
        pets = {}
        for surepy_entity in self.data.values():
            if surepy_entity.type == EntityType.PET and surepy_entity.name:
                pets[surepy_entity.name] = surepy_entity.id
        return pets

    async def handle_set_pet_location(self, call: ServiceCall) -> None:
        """Call when setting the pet location."""
        pet_name = call.data[ATTR_PET_NAME]
        location = call.data[ATTR_LOCATION]
        device_id = self.get_pets()[pet_name]
        await self.surepy.sac.set_pet_location(device_id, Location[location.upper()])
        await self.async_request_refresh()
