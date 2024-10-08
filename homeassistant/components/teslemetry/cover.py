"""Cover platform for Teslemetry integration."""

from __future__ import annotations

from typing import Any

from tesla_fleet_api.const import Scope, SunRoofCommand, Trunk, WindowCommand

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TeslemetryConfigEntry
from .entity import TeslemetryVehicleEntity
from .helpers import handle_vehicle_command
from .models import TeslemetryVehicleData

OPEN = 1
CLOSED = 0

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Teslemetry cover platform from a config entry."""

    async_add_entities(
        klass(vehicle, entry.runtime_data.scopes)
        for (klass) in (
            TeslemetryWindowEntity,
            TeslemetryChargePortEntity,
            TeslemetryFrontTrunkEntity,
            TeslemetryRearTrunkEntity,
            TeslemetrySunroofEntity,
        )
        for vehicle in entry.runtime_data.vehicles
    )


class TeslemetryWindowEntity(TeslemetryVehicleEntity, CoverEntity):
    """Cover entity for the windows."""

    _attr_device_class = CoverDeviceClass.WINDOW

    def __init__(self, data: TeslemetryVehicleData, scopes: list[Scope]) -> None:
        """Initialize the cover."""
        super().__init__(data, "windows")
        self.scoped = Scope.VEHICLE_CMDS in scopes
        self._attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        )
        if not self.scoped:
            self._attr_supported_features = CoverEntityFeature(0)

    def _async_update_attrs(self) -> None:
        """Update the entity attributes."""
        fd = self.get("vehicle_state_fd_window")
        fp = self.get("vehicle_state_fp_window")
        rd = self.get("vehicle_state_rd_window")
        rp = self.get("vehicle_state_rp_window")

        # Any open set to open
        if OPEN in (fd, fp, rd, rp):
            self._attr_is_closed = False
        # All closed set to closed
        elif CLOSED == fd == fp == rd == rp:
            self._attr_is_closed = True
        # Otherwise, set to unknown
        else:
            self._attr_is_closed = None

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Vent windows."""
        self.raise_for_scope(Scope.VEHICLE_CMDS)
        await self.wake_up_if_asleep()
        await handle_vehicle_command(
            self.api.window_control(command=WindowCommand.VENT)
        )
        self._attr_is_closed = False
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close windows."""
        self.raise_for_scope(Scope.VEHICLE_CMDS)
        await self.wake_up_if_asleep()
        await handle_vehicle_command(
            self.api.window_control(command=WindowCommand.CLOSE)
        )
        self._attr_is_closed = True
        self.async_write_ha_state()


class TeslemetryChargePortEntity(TeslemetryVehicleEntity, CoverEntity):
    """Cover entity for the charge port."""

    _attr_device_class = CoverDeviceClass.DOOR

    def __init__(self, vehicle: TeslemetryVehicleData, scopes: list[Scope]) -> None:
        """Initialize the cover."""
        super().__init__(vehicle, "charge_state_charge_port_door_open")
        self.scoped = any(
            scope in scopes
            for scope in (Scope.VEHICLE_CMDS, Scope.VEHICLE_CHARGING_CMDS)
        )
        self._attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        )
        if not self.scoped:
            self._attr_supported_features = CoverEntityFeature(0)

    def _async_update_attrs(self) -> None:
        """Update the entity attributes."""
        self._attr_is_closed = not self._value

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open charge port."""
        self.raise_for_scope(Scope.VEHICLE_CHARGING_CMDS)
        await self.wake_up_if_asleep()
        await handle_vehicle_command(self.api.charge_port_door_open())
        self._attr_is_closed = False
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close charge port."""
        self.raise_for_scope(Scope.VEHICLE_CHARGING_CMDS)
        await self.wake_up_if_asleep()
        await handle_vehicle_command(self.api.charge_port_door_close())
        self._attr_is_closed = True
        self.async_write_ha_state()


class TeslemetryFrontTrunkEntity(TeslemetryVehicleEntity, CoverEntity):
    """Cover entity for the front trunk."""

    _attr_device_class = CoverDeviceClass.DOOR

    def __init__(self, vehicle: TeslemetryVehicleData, scopes: list[Scope]) -> None:
        """Initialize the cover."""
        super().__init__(vehicle, "vehicle_state_ft")

        self.scoped = Scope.VEHICLE_CMDS in scopes
        self._attr_supported_features = CoverEntityFeature.OPEN
        if not self.scoped:
            self._attr_supported_features = CoverEntityFeature(0)

    def _async_update_attrs(self) -> None:
        """Update the entity attributes."""
        self._attr_is_closed = self._value == CLOSED

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open front trunk."""
        self.raise_for_scope(Scope.VEHICLE_CMDS)
        await self.wake_up_if_asleep()
        await handle_vehicle_command(self.api.actuate_trunk(Trunk.FRONT))
        self._attr_is_closed = False
        self.async_write_ha_state()


class TeslemetryRearTrunkEntity(TeslemetryVehicleEntity, CoverEntity):
    """Cover entity for the rear trunk."""

    _attr_device_class = CoverDeviceClass.DOOR

    def __init__(self, vehicle: TeslemetryVehicleData, scopes: list[Scope]) -> None:
        """Initialize the cover."""
        super().__init__(vehicle, "vehicle_state_rt")

        self.scoped = Scope.VEHICLE_CMDS in scopes
        self._attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        )
        if not self.scoped:
            self._attr_supported_features = CoverEntityFeature(0)

    def _async_update_attrs(self) -> None:
        """Update the entity attributes."""
        value = self._value
        if value == CLOSED:
            self._attr_is_closed = True
        elif value == OPEN:
            self._attr_is_closed = False
        else:
            self._attr_is_closed = None

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open rear trunk."""
        if self.is_closed is not False:
            self.raise_for_scope(Scope.VEHICLE_CMDS)
            await self.wake_up_if_asleep()
            await handle_vehicle_command(self.api.actuate_trunk(Trunk.REAR))
            self._attr_is_closed = False
            self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close rear trunk."""
        if self.is_closed is not True:
            self.raise_for_scope(Scope.VEHICLE_CMDS)
            await self.wake_up_if_asleep()
            await handle_vehicle_command(self.api.actuate_trunk(Trunk.REAR))
            self._attr_is_closed = True
            self.async_write_ha_state()


class TeslemetrySunroofEntity(TeslemetryVehicleEntity, CoverEntity):
    """Cover entity for the sunroof."""

    _attr_device_class = CoverDeviceClass.WINDOW
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )
    _attr_entity_registry_enabled_default = False

    def __init__(self, vehicle: TeslemetryVehicleData, scopes: list[Scope]) -> None:
        """Initialize the sensor."""
        super().__init__(vehicle, "vehicle_state_sun_roof_state")

        self.scoped = Scope.VEHICLE_CMDS in scopes
        if not self.scoped:
            self._attr_supported_features = CoverEntityFeature(0)

    def _async_update_attrs(self) -> None:
        """Update the entity attributes."""
        value = self._value
        if value in (None, "unknown"):
            self._attr_is_closed = None
        else:
            self._attr_is_closed = value == "closed"

        self._attr_current_cover_position = self.get(
            "vehicle_state_sun_roof_percent_open"
        )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open sunroof."""
        self.raise_for_scope(Scope.VEHICLE_CMDS)
        await self.wake_up_if_asleep()
        await handle_vehicle_command(self.api.sun_roof_control(SunRoofCommand.VENT))
        self._attr_is_closed = False
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close sunroof."""
        self.raise_for_scope(Scope.VEHICLE_CMDS)
        await self.wake_up_if_asleep()
        await handle_vehicle_command(self.api.sun_roof_control(SunRoofCommand.CLOSE))
        self._attr_is_closed = True
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Close sunroof."""
        self.raise_for_scope(Scope.VEHICLE_CMDS)
        await self.wake_up_if_asleep()
        await handle_vehicle_command(self.api.sun_roof_control(SunRoofCommand.STOP))
        self._attr_is_closed = False
        self.async_write_ha_state()
