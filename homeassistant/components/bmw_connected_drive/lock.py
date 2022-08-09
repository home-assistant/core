"""Support for BMW car locks with BMW ConnectedDrive."""
from __future__ import annotations

import logging
from typing import Any

from bimmer_connected.vehicle import MyBMWVehicle
from bimmer_connected.vehicle.doors_windows import LockState

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BMWBaseEntity
from .const import DOMAIN
from .coordinator import BMWDataUpdateCoordinator

DOOR_LOCK_STATE = "door_lock_state"
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MyBMW lock from config entry."""
    coordinator: BMWDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[BMWLock] = []

    for vehicle in coordinator.account.vehicles:
        if not coordinator.read_only:
            entities.append(BMWLock(coordinator, vehicle, "lock", "BMW lock"))
    async_add_entities(entities)


class BMWLock(BMWBaseEntity, LockEntity):
    """Representation of a MyBMW vehicle lock."""

    def __init__(
        self,
        coordinator: BMWDataUpdateCoordinator,
        vehicle: MyBMWVehicle,
        attribute: str,
        sensor_name: str,
    ) -> None:
        """Initialize the lock."""
        super().__init__(coordinator, vehicle)

        self._attribute = attribute
        self._attr_name = f"{vehicle.name} {attribute}"
        self._attr_unique_id = f"{vehicle.vin}-{attribute}"
        self._sensor_name = sensor_name
        self.door_lock_state_available = DOOR_LOCK_STATE in vehicle.available_attributes

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the car."""
        _LOGGER.debug("%s: locking doors", self.vehicle.name)
        # Only update the HA state machine if the vehicle reliably reports its lock state
        if self.door_lock_state_available:
            # Optimistic state set here because it takes some time before the
            # update callback response
            self._attr_is_locked = True
            self.async_write_ha_state()
        await self.vehicle.remote_services.trigger_remote_door_lock()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the car."""
        _LOGGER.debug("%s: unlocking doors", self.vehicle.name)
        # Only update the HA state machine if the vehicle reliably reports its lock state
        if self.door_lock_state_available:
            # Optimistic state set here because it takes some time before the
            # update callback response
            self._attr_is_locked = False
            self.async_write_ha_state()
        await self.vehicle.remote_services.trigger_remote_door_unlock()

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
            self._attr_extra_state_attributes = dict(
                self._attrs,
                **{
                    "door_lock_state": self.vehicle.doors_and_windows.door_lock_state.value,
                },
            )

        super()._handle_coordinator_update()
