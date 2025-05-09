"""Lock platform for Teslemetry integration."""

from __future__ import annotations

from itertools import chain
from typing import Any

from tesla_fleet_api.const import Scope
from tesla_fleet_api.teslemetry import Vehicle

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import TeslemetryConfigEntry
from .const import DOMAIN
from .entity import (
    TeslemetryRootEntity,
    TeslemetryVehiclePollingEntity,
    TeslemetryVehicleStreamEntity,
)
from .helpers import handle_vehicle_command
from .models import TeslemetryVehicleData

ENGAGED = "Engaged"

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Teslemetry lock platform from a config entry."""

    async_add_entities(
        chain(
            (
                TeslemetryVehiclePollingVehicleLockEntity(
                    vehicle, Scope.VEHICLE_CMDS in entry.runtime_data.scopes
                )
                if vehicle.api.pre2021 or vehicle.firmware < "2024.26"
                else TeslemetryStreamingVehicleLockEntity(
                    vehicle, Scope.VEHICLE_CMDS in entry.runtime_data.scopes
                )
                for vehicle in entry.runtime_data.vehicles
            ),
            (
                TeslemetryVehiclePollingCableLockEntity(
                    vehicle, Scope.VEHICLE_CMDS in entry.runtime_data.scopes
                )
                if vehicle.api.pre2021 or vehicle.firmware < "2024.26"
                else TeslemetryStreamingCableLockEntity(
                    vehicle, Scope.VEHICLE_CMDS in entry.runtime_data.scopes
                )
                for vehicle in entry.runtime_data.vehicles
            ),
        )
    )


class TeslemetryVehicleLockEntity(TeslemetryRootEntity, LockEntity):
    """Base vehicle lock entity for Teslemetry."""

    api: Vehicle

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the doors."""
        self.raise_for_scope(Scope.VEHICLE_CMDS)

        await handle_vehicle_command(self.api.door_lock())
        self._attr_is_locked = True
        self.async_write_ha_state()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the doors."""
        self.raise_for_scope(Scope.VEHICLE_CMDS)

        await handle_vehicle_command(self.api.door_unlock())
        self._attr_is_locked = False
        self.async_write_ha_state()


class TeslemetryVehiclePollingVehicleLockEntity(
    TeslemetryVehiclePollingEntity, TeslemetryVehicleLockEntity
):
    """Polling vehicle lock entity for Teslemetry."""

    def __init__(self, data: TeslemetryVehicleData, scoped: bool) -> None:
        """Initialize the sensor."""
        super().__init__(
            data,
            "vehicle_state_locked",
        )
        self.scoped = scoped

    def _async_update_attrs(self) -> None:
        """Update entity attributes."""
        self._attr_is_locked = self._value


class TeslemetryStreamingVehicleLockEntity(
    TeslemetryVehicleStreamEntity, TeslemetryVehicleLockEntity, RestoreEntity
):
    """Streaming vehicle lock entity for Teslemetry."""

    def __init__(self, data: TeslemetryVehicleData, scoped: bool) -> None:
        """Initialize the sensor."""
        super().__init__(
            data,
            "vehicle_state_locked",
        )
        self.scoped = scoped

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        # Restore state
        if (state := await self.async_get_last_state()) is not None:
            if state.state == "locked":
                self._attr_is_locked = True
            elif state.state == "unlocked":
                self._attr_is_locked = False

        # Add streaming listener
        self.async_on_remove(self.vehicle.stream_vehicle.listen_Locked(self._callback))

    def _callback(self, value: bool | None) -> None:
        """Update entity attributes."""
        self._attr_is_locked = value
        self.async_write_ha_state()


class TeslemetryCableLockEntity(TeslemetryRootEntity, LockEntity):
    """Base cable Lock entity for Teslemetry."""

    api: Vehicle

    async def async_lock(self, **kwargs: Any) -> None:
        """Charge cable Lock cannot be manually locked."""
        raise ServiceValidationError(
            "Insert cable to lock",
            translation_domain=DOMAIN,
            translation_key="no_cable",
        )

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock charge cable lock."""
        self.raise_for_scope(Scope.VEHICLE_CMDS)

        await handle_vehicle_command(self.api.charge_port_door_open())
        self._attr_is_locked = False
        self.async_write_ha_state()


class TeslemetryVehiclePollingCableLockEntity(
    TeslemetryVehiclePollingEntity, TeslemetryCableLockEntity
):
    """Polling cable lock entity for Teslemetry."""

    def __init__(
        self,
        data: TeslemetryVehicleData,
        scoped: bool,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            data,
            "charge_state_charge_port_latch",
        )
        self.scoped = scoped

    def _async_update_attrs(self) -> None:
        """Update entity attributes."""
        if self._value is None:
            self._attr_is_locked = None
        self._attr_is_locked = self._value == ENGAGED


class TeslemetryStreamingCableLockEntity(
    TeslemetryVehicleStreamEntity, TeslemetryCableLockEntity, RestoreEntity
):
    """Streaming cable lock entity for Teslemetry."""

    def __init__(
        self,
        data: TeslemetryVehicleData,
        scoped: bool,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            data,
            "charge_state_charge_port_latch",
        )
        self.scoped = scoped

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        # Restore state
        if (state := await self.async_get_last_state()) is not None:
            if state.state == "locked":
                self._attr_is_locked = True
            elif state.state == "unlocked":
                self._attr_is_locked = False

        # Add streaming listener
        self.async_on_remove(
            self.vehicle.stream_vehicle.listen_ChargePortLatch(self._callback)
        )

    def _callback(self, value: str | None) -> None:
        """Update entity attributes."""
        self._attr_is_locked = None if value is None else value == ENGAGED
        self.async_write_ha_state()
