"""Support for BMW car locks with BMW ConnectedDrive."""

from __future__ import annotations

import logging
from typing import Any

from bimmer_connected.models import MyBMWAPIError
from bimmer_connected.vehicle import MyBMWVehicle
from bimmer_connected.vehicle.doors_windows import LockState

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN as BMW_DOMAIN, BMWConfigEntry
from .coordinator import BMWDataUpdateCoordinator
from .entity import BMWBaseEntity

PARALLEL_UPDATES = 1

DOOR_LOCK_STATE = "door_lock_state"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BMWConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MyBMW lock from config entry."""
    coordinator = config_entry.runtime_data

    if not coordinator.read_only:
        async_add_entities(
            BMWLock(coordinator, vehicle) for vehicle in coordinator.account.vehicles
        )


class BMWLock(BMWBaseEntity, LockEntity):
    """Representation of a MyBMW vehicle lock."""

    _attr_translation_key = "lock"

    def __init__(
        self,
        coordinator: BMWDataUpdateCoordinator,
        vehicle: MyBMWVehicle,
    ) -> None:
        """Initialize the lock."""
        super().__init__(coordinator, vehicle)

        self._attr_unique_id = f"{vehicle.vin}-lock"
        self.door_lock_state_available = vehicle.is_lsc_enabled

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the car."""
        _LOGGER.debug("%s: locking doors", self.vehicle.name)
        # Only update the HA state machine if the vehicle reliably reports its lock state
        if self.door_lock_state_available:
            # Optimistic state set here because it takes some time before the
            # update callback response
            self._attr_is_locked = True
            self.async_write_ha_state()
        try:
            await self.vehicle.remote_services.trigger_remote_door_lock()
        except MyBMWAPIError as ex:
            # Set the state to unknown if the command fails
            self._attr_is_locked = None
            self.async_write_ha_state()
            raise HomeAssistantError(
                translation_domain=BMW_DOMAIN,
                translation_key="remote_service_error",
                translation_placeholders={"exception": str(ex)},
            ) from ex
        finally:
            # Always update the listeners to get the latest state
            self.coordinator.async_update_listeners()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the car."""
        _LOGGER.debug("%s: unlocking doors", self.vehicle.name)
        # Only update the HA state machine if the vehicle reliably reports its lock state
        if self.door_lock_state_available:
            # Optimistic state set here because it takes some time before the
            # update callback response
            self._attr_is_locked = False
            self.async_write_ha_state()
        try:
            await self.vehicle.remote_services.trigger_remote_door_unlock()
        except MyBMWAPIError as ex:
            # Set the state to unknown if the command fails
            self._attr_is_locked = None
            self.async_write_ha_state()
            raise HomeAssistantError(
                translation_domain=BMW_DOMAIN,
                translation_key="remote_service_error",
                translation_placeholders={"exception": str(ex)},
            ) from ex
        finally:
            # Always update the listeners to get the latest state
            self.coordinator.async_update_listeners()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug("Updating lock data of %s", self.vehicle.name)

        # Only update the HA state machine if the vehicle reliably reports its lock state
        if self.door_lock_state_available:
            self._attr_is_locked = self.vehicle.doors_and_windows.door_lock_state in {
                LockState.LOCKED,
                LockState.SECURED,
            }
            self._attr_extra_state_attributes = {
                DOOR_LOCK_STATE: self.vehicle.doors_and_windows.door_lock_state.value
            }

        super()._handle_coordinator_update()
