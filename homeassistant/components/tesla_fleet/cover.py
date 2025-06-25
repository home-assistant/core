"""Cover platform for Tesla Fleet integration."""

from __future__ import annotations

from typing import Any

from tesla_fleet_api.const import Scope, SunRoofCommand, Trunk, WindowCommand

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TeslaFleetConfigEntry
from .entity import TeslaFleetVehicleEntity
from .helpers import handle_vehicle_command
from .models import TeslaFleetVehicleData

OPEN = 1
CLOSED = 0

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeslaFleetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the TeslaFleet cover platform from a config entry."""

    async_add_entities(
        klass(vehicle, entry.runtime_data.scopes)
        for (klass) in (
            TeslaFleetWindowEntity,
            TeslaFleetChargePortEntity,
            TeslaFleetFrontTrunkEntity,
            TeslaFleetRearTrunkEntity,
            TeslaFleetSunroofEntity,
        )
        for vehicle in entry.runtime_data.vehicles
    )


class TeslaFleetWindowEntity(TeslaFleetVehicleEntity, CoverEntity):
    """Cover entity for the windows."""

    _attr_device_class = CoverDeviceClass.WINDOW

    def __init__(self, data: TeslaFleetVehicleData, scopes: list[Scope]) -> None:
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
        await self.wake_up_if_asleep()
        await handle_vehicle_command(
            self.api.window_control(command=WindowCommand.VENT)
        )
        self._attr_is_closed = False
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close windows."""
        await self.wake_up_if_asleep()
        await handle_vehicle_command(
            self.api.window_control(command=WindowCommand.CLOSE)
        )
        self._attr_is_closed = True
        self.async_write_ha_state()


class TeslaFleetChargePortEntity(TeslaFleetVehicleEntity, CoverEntity):
    """Cover entity for the charge port."""

    _attr_device_class = CoverDeviceClass.DOOR

    def __init__(self, vehicle: TeslaFleetVehicleData, scopes: list[Scope]) -> None:
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
        await self.wake_up_if_asleep()
        await handle_vehicle_command(self.api.charge_port_door_open())
        self._attr_is_closed = False
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close charge port."""
        await self.wake_up_if_asleep()
        await handle_vehicle_command(self.api.charge_port_door_close())
        self._attr_is_closed = True
        self.async_write_ha_state()


class TeslaFleetFrontTrunkEntity(TeslaFleetVehicleEntity, CoverEntity):
    """Cover entity for the front trunk."""

    _attr_device_class = CoverDeviceClass.DOOR

    def __init__(self, vehicle: TeslaFleetVehicleData, scopes: list[Scope]) -> None:
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
        await self.wake_up_if_asleep()
        await handle_vehicle_command(self.api.actuate_trunk(Trunk.FRONT))
        self._attr_is_closed = False
        self.async_write_ha_state()


class TeslaFleetRearTrunkEntity(TeslaFleetVehicleEntity, CoverEntity):
    """Cover entity for the rear trunk."""

    _attr_device_class = CoverDeviceClass.DOOR

    def __init__(self, vehicle: TeslaFleetVehicleData, scopes: list[Scope]) -> None:
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
        self._attr_is_closed = self._value == CLOSED

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open rear trunk."""
        if self.is_closed is not False:
            await self.wake_up_if_asleep()
            await handle_vehicle_command(self.api.actuate_trunk(Trunk.REAR))
            self._attr_is_closed = False
            self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close rear trunk."""
        if self.is_closed is not True:
            await self.wake_up_if_asleep()
            await handle_vehicle_command(self.api.actuate_trunk(Trunk.REAR))
            self._attr_is_closed = True
            self.async_write_ha_state()


class TeslaFleetSunroofEntity(TeslaFleetVehicleEntity, CoverEntity):
    """Cover entity for the sunroof."""

    _attr_device_class = CoverDeviceClass.WINDOW
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )
    _attr_entity_registry_enabled_default = False

    def __init__(self, vehicle: TeslaFleetVehicleData, scopes: list[Scope]) -> None:
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
        await self.wake_up_if_asleep()
        await handle_vehicle_command(self.api.sun_roof_control(SunRoofCommand.VENT))
        self._attr_is_closed = False
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close sunroof."""
        await self.wake_up_if_asleep()
        await handle_vehicle_command(self.api.sun_roof_control(SunRoofCommand.CLOSE))
        self._attr_is_closed = True
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Close sunroof."""
        await self.wake_up_if_asleep()
        await handle_vehicle_command(self.api.sun_roof_control(SunRoofCommand.STOP))
        self._attr_is_closed = False
        self.async_write_ha_state()
