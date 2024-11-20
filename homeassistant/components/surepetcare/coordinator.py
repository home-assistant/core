"""Coordinator for the surepetcare integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from surepy import Surepy, SurepyEntity
from surepy.enums import EntityType, Location, LockState
from surepy.exceptions import SurePetcareAuthenticationError, SurePetcareError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_FLAP_ID,
    ATTR_LOCATION,
    ATTR_LOCK_STATE,
    ATTR_PET_NAME,
    DOMAIN,
    SURE_API_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=3)


class SurePetcareDataCoordinator(DataUpdateCoordinator[dict[int, SurepyEntity]]):
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
