"""Cover platform for Teslemetry integration."""

from __future__ import annotations

from itertools import chain
from typing import Any

from tesla_fleet_api.const import Scope, SunRoofCommand, Trunk, WindowCommand
from teslemetry_stream import Signal
from teslemetry_stream.const import WindowState

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import TeslemetryConfigEntry
from .entity import (
    TeslemetryRootEntity,
    TeslemetryVehicleEntity,
    TeslemetryVehicleStreamEntity,
)
from .helpers import handle_vehicle_command
from .models import TeslemetryVehicleData

OPEN = 1
CLOSED = 0

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Teslemetry cover platform from a config entry."""

    async_add_entities(
        chain(
            (
                TeslemetryPollingWindowEntity(vehicle, entry.runtime_data.scopes)
                if vehicle.api.pre2021 or vehicle.firmware < "2024.26"
                else TeslemetryStreamingWindowEntity(vehicle, entry.runtime_data.scopes)
                for vehicle in entry.runtime_data.vehicles
            ),
            (
                TeslemetryPollingChargePortEntity(vehicle, entry.runtime_data.scopes)
                if vehicle.api.pre2021 or vehicle.firmware < "2024.44.25"
                else TeslemetryStreamingChargePortEntity(
                    vehicle, entry.runtime_data.scopes
                )
                for vehicle in entry.runtime_data.vehicles
            ),
            (
                TeslemetryPollingFrontTrunkEntity(vehicle, entry.runtime_data.scopes)
                if vehicle.api.pre2021 or vehicle.firmware < "2024.26"
                else TeslemetryStreamingFrontTrunkEntity(
                    vehicle, entry.runtime_data.scopes
                )
                for vehicle in entry.runtime_data.vehicles
            ),
            (
                TeslemetryPollingRearTrunkEntity(vehicle, entry.runtime_data.scopes)
                if vehicle.api.pre2021 or vehicle.firmware < "2024.26"
                else TeslemetryStreamingRearTrunkEntity(
                    vehicle, entry.runtime_data.scopes
                )
                for vehicle in entry.runtime_data.vehicles
            ),
            (
                TeslemetrySunroofEntity(vehicle, entry.runtime_data.scopes)
                for vehicle in entry.runtime_data.vehicles
                if vehicle.coordinator.data.get("vehicle_config_sun_roof_installed")
            ),
        )
    )


class CoverRestoreEntity(RestoreEntity, CoverEntity):
    """Restore class for cover entities."""

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        if (state := await self.async_get_last_state()) is not None:
            if state.state == "open":
                self._attr_is_closed = False
            elif state.state == "closed":
                self._attr_is_closed = True


class TeslemetryWindowEntity(TeslemetryRootEntity, CoverEntity):
    """Base class for window cover entities."""

    _attr_device_class = CoverDeviceClass.WINDOW
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Vent windows."""
        self.raise_for_scope(Scope.VEHICLE_CMDS)

        await handle_vehicle_command(
            self.api.window_control(command=WindowCommand.VENT)
        )
        self._attr_is_closed = False
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close windows."""
        self.raise_for_scope(Scope.VEHICLE_CMDS)

        await handle_vehicle_command(
            self.api.window_control(command=WindowCommand.CLOSE)
        )
        self._attr_is_closed = True
        self.async_write_ha_state()


class TeslemetryPollingWindowEntity(
    TeslemetryVehicleEntity, TeslemetryWindowEntity, CoverEntity
):
    """Polling cover entity for windows."""

    def __init__(self, data: TeslemetryVehicleData, scopes: list[Scope]) -> None:
        """Initialize the cover."""
        super().__init__(data, "windows")
        self.scoped = Scope.VEHICLE_CMDS in scopes
        if not self.scoped:
            self._attr_supported_features = CoverEntityFeature(0)

    def _async_update_attrs(self) -> None:
        """Update the entity attributes."""
        fd = self.get("vehicle_state_fd_window")
        fp = self.get("vehicle_state_fp_window")
        rd = self.get("vehicle_state_rd_window")
        rp = self.get("vehicle_state_rp_window")

        if OPEN in (fd, fp, rd, rp):
            self._attr_is_closed = False
        elif None in (fd, fp, rd, rp):
            self._attr_is_closed = None
        else:
            self._attr_is_closed = True


class TeslemetryStreamingWindowEntity(
    TeslemetryVehicleStreamEntity, TeslemetryWindowEntity, CoverRestoreEntity
):
    """Streaming cover entity for windows."""

    fd: bool | None = None
    fp: bool | None = None
    rd: bool | None = None
    rp: bool | None = None

    def __init__(self, data: TeslemetryVehicleData, scopes: list[Scope]) -> None:
        """Initialize the cover."""
        super().__init__(
            data,
            "windows",
        )
        self.scoped = Scope.VEHICLE_CMDS in scopes
        if not self.scoped:
            self._attr_supported_features = CoverEntityFeature(0)
        self._attr_is_closed = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.stream.async_add_listener(
                self._handle_stream_update,
                {"vin": self.vin, "data": {self.streaming_key: None}},
            )
        )
        for signal in (
            Signal.FD_WINDOW,
            Signal.FP_WINDOW,
            Signal.RD_WINDOW,
            Signal.RP_WINDOW,
        ):
            self.vehicle.config_entry.async_create_background_task(
                self.hass,
                self.add_field(signal),
                f"Adding field {signal} to {self.vehicle.vin}",
            )

    def _handle_stream_update(self, data) -> None:
        """Update the entity attributes."""

        if value := data.get(Signal.FD_WINDOW):
            self.fd = WindowState.get(value) == "closed"
        if value := data.get(Signal.FP_WINDOW):
            self.fp = WindowState.get(value) == "closed"
        if value := data.get(Signal.RD_WINDOW):
            self.rd = WindowState.get(value) == "closed"
        if value := data.get(Signal.RP_WINDOW):
            self.rp = WindowState.get(value) == "closed"

        if False in (self.fd, self.fp, self.rd, self.rp):
            self._attr_is_closed = False
        elif None in (self.fd, self.fp, self.rd, self.rp):
            self._attr_is_closed = None
        else:
            self._attr_is_closed = True

        self.async_write_ha_state()


class TeslemetryChargePortEntity(
    TeslemetryRootEntity,
    CoverEntity,
):
    """Base class for for charge port cover entities."""

    _attr_device_class = CoverDeviceClass.DOOR
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open charge port."""
        self.raise_for_scope(Scope.VEHICLE_CHARGING_CMDS)

        await handle_vehicle_command(self.api.charge_port_door_open())
        self._attr_is_closed = False
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close charge port."""
        self.raise_for_scope(Scope.VEHICLE_CHARGING_CMDS)

        await handle_vehicle_command(self.api.charge_port_door_close())
        self._attr_is_closed = True
        self.async_write_ha_state()


class TeslemetryPollingChargePortEntity(
    TeslemetryVehicleEntity, TeslemetryChargePortEntity
):
    """Polling cover entity for the charge port."""

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


class TeslemetryStreamingChargePortEntity(
    TeslemetryVehicleStreamEntity, TeslemetryChargePortEntity, CoverRestoreEntity
):
    """Streaming cover entity for the charge port."""

    def __init__(self, vehicle: TeslemetryVehicleData, scopes: list[Scope]) -> None:
        """Initialize the sensor."""
        super().__init__(
            vehicle,
            "charge_state_charge_port_door_open",
        )
        self.scoped = any(
            scope in scopes
            for scope in (Scope.VEHICLE_CMDS, Scope.VEHICLE_CHARGING_CMDS)
        )
        if not self.scoped:
            self._attr_supported_features = CoverEntityFeature(0)
        self._attr_is_closed = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.vehicle.stream_vehicle.listen_ChargePortDoorOpen(
                self._async_value_from_stream
            )
        )

    def _async_value_from_stream(self, value: bool | None) -> None:
        """Update the value of the entity."""
        self._attr_is_closed = None if value is None else not value
        self.async_write_ha_state()


class TeslemetryFrontTrunkEntity(TeslemetryRootEntity, CoverEntity):
    """Base class for the front trunk cover entities."""

    _attr_device_class = CoverDeviceClass.DOOR
    _attr_supported_features = CoverEntityFeature.OPEN

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open front trunk."""
        self.raise_for_scope(Scope.VEHICLE_CMDS)

        await handle_vehicle_command(self.api.actuate_trunk(Trunk.FRONT))
        self._attr_is_closed = False
        self.async_write_ha_state()

    # In the future this could be extended to add aftermarket close support through a option flow


class TeslemetryPollingFrontTrunkEntity(
    TeslemetryVehicleEntity, TeslemetryFrontTrunkEntity
):
    """Polling cover entity for the front trunk."""

    def __init__(self, vehicle: TeslemetryVehicleData, scopes: list[Scope]) -> None:
        """Initialize the cover."""
        self.scoped = Scope.VEHICLE_CMDS in scopes
        if not self.scoped:
            self._attr_supported_features = CoverEntityFeature(0)
        super().__init__(vehicle, "vehicle_state_ft")

    def _async_update_attrs(self) -> None:
        """Update the entity attributes."""
        self._attr_is_closed = self._value == CLOSED


class TeslemetryStreamingFrontTrunkEntity(
    TeslemetryVehicleStreamEntity, TeslemetryFrontTrunkEntity, CoverRestoreEntity
):
    """Streaming cover entity for the front trunk."""

    def __init__(self, vehicle: TeslemetryVehicleData, scopes: list[Scope]) -> None:
        """Initialize the sensor."""
        super().__init__(vehicle, "vehicle_state_ft")
        self.scoped = Scope.VEHICLE_CMDS in scopes
        if not self.scoped:
            self._attr_supported_features = CoverEntityFeature(0)
        self._attr_is_closed = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.vehicle.stream_vehicle.listen_TrunkFront(self._async_value_from_stream)
        )

    def _async_value_from_stream(self, value: bool | None) -> None:
        """Update the entity attributes."""

        self._attr_is_closed = None if value is None else not value
        self.async_write_ha_state()


class TeslemetryRearTrunkEntity(TeslemetryRootEntity, CoverEntity):
    """Cover entity for the rear trunk."""

    _attr_device_class = CoverDeviceClass.DOOR
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open rear trunk."""
        if self.is_closed is not False:
            self.raise_for_scope(Scope.VEHICLE_CMDS)

            await handle_vehicle_command(self.api.actuate_trunk(Trunk.REAR))
            self._attr_is_closed = False
            self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close rear trunk."""
        if self.is_closed is not True:
            self.raise_for_scope(Scope.VEHICLE_CMDS)

            await handle_vehicle_command(self.api.actuate_trunk(Trunk.REAR))
            self._attr_is_closed = True
            self.async_write_ha_state()


class TeslemetryPollingRearTrunkEntity(
    TeslemetryVehicleEntity, TeslemetryRearTrunkEntity
):
    """Base class for the rear trunk cover entities."""

    def __init__(self, vehicle: TeslemetryVehicleData, scopes: list[Scope]) -> None:
        """Initialize the sensor."""
        self.scoped = Scope.VEHICLE_CMDS in scopes
        if not self.scoped:
            self._attr_supported_features = CoverEntityFeature(0)
        super().__init__(vehicle, "vehicle_state_rt")

    def _async_update_attrs(self) -> None:
        """Update the entity attributes."""
        self._attr_is_closed = self._value == CLOSED


class TeslemetryStreamingRearTrunkEntity(
    TeslemetryVehicleStreamEntity, TeslemetryRearTrunkEntity, CoverRestoreEntity
):
    """Polling cover entity for the rear trunk."""

    def __init__(self, vehicle: TeslemetryVehicleData, scopes: list[Scope]) -> None:
        """Initialize the cover."""
        super().__init__(vehicle, "vehicle_state_rt")
        self.scoped = Scope.VEHICLE_CMDS in scopes
        if not self.scoped:
            self._attr_supported_features = CoverEntityFeature(0)
        self._attr_is_closed = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.vehicle.stream_vehicle.listen_TrunkRear(self._async_value_from_stream)
        )

    def _async_value_from_stream(self, value: bool | None) -> None:
        """Update the entity attributes."""

        self._attr_is_closed = None if value is None else not value


class TeslemetrySunroofEntity(TeslemetryVehicleEntity, CoverEntity):
    """Cover entity for the sunroof."""

    _attr_device_class = CoverDeviceClass.WINDOW
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )
    _attr_entity_registry_enabled_default = False

    def __init__(self, vehicle: TeslemetryVehicleData, scopes: list[Scope]) -> None:
        """Initialize the cover."""
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
        await handle_vehicle_command(self.api.sun_roof_control(SunRoofCommand.VENT))
        self._attr_is_closed = False
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close sunroof."""
        self.raise_for_scope(Scope.VEHICLE_CMDS)
        await handle_vehicle_command(self.api.sun_roof_control(SunRoofCommand.CLOSE))
        self._attr_is_closed = True
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Close sunroof."""
        self.raise_for_scope(Scope.VEHICLE_CMDS)
        await handle_vehicle_command(self.api.sun_roof_control(SunRoofCommand.STOP))
        self._attr_is_closed = False
        self.async_write_ha_state()
