"""Cover platform for Tessie integration."""

from __future__ import annotations

from itertools import chain
from typing import Any

from tessie_api import (
    close_charge_port,
    close_sunroof,
    close_windows,
    open_close_rear_trunk,
    open_front_trunk,
    open_unlock_charge_port,
    vent_sunroof,
    vent_windows,
)

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TessieConfigEntry
from .const import TessieCoverStates
from .entity import TessieEntity
from .models import TessieVehicleData

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TessieConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tessie sensor platform from a config entry."""
    data = entry.runtime_data

    async_add_entities(
        chain(
            (
                klass(vehicle)
                for klass in (
                    TessieWindowEntity,
                    TessieChargePortEntity,
                    TessieFrontTrunkEntity,
                    TessieRearTrunkEntity,
                )
                for vehicle in data.vehicles
            ),
            (
                TessieSunroofEntity(vehicle)
                for vehicle in data.vehicles
                if vehicle.data_coordinator.data.get(
                    "vehicle_config_sun_roof_installed"
                )
            ),
        )
    )


class TessieWindowEntity(TessieEntity, CoverEntity):
    """Cover entity for current charge."""

    _attr_device_class = CoverDeviceClass.WINDOW
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    def __init__(self, vehicle: TessieVehicleData) -> None:
        """Initialize the sensor."""
        super().__init__(vehicle, "windows")

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        return (
            self.get("vehicle_state_fd_window") == TessieCoverStates.CLOSED
            and self.get("vehicle_state_fp_window") == TessieCoverStates.CLOSED
            and self.get("vehicle_state_rd_window") == TessieCoverStates.CLOSED
            and self.get("vehicle_state_rp_window") == TessieCoverStates.CLOSED
        )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open windows."""
        await self.run(vent_windows)
        self.set(
            ("vehicle_state_fd_window", TessieCoverStates.OPEN),
            ("vehicle_state_fp_window", TessieCoverStates.OPEN),
            ("vehicle_state_rd_window", TessieCoverStates.OPEN),
            ("vehicle_state_rp_window", TessieCoverStates.OPEN),
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close windows."""
        await self.run(close_windows)
        self.set(
            ("vehicle_state_fd_window", TessieCoverStates.CLOSED),
            ("vehicle_state_fp_window", TessieCoverStates.CLOSED),
            ("vehicle_state_rd_window", TessieCoverStates.CLOSED),
            ("vehicle_state_rp_window", TessieCoverStates.CLOSED),
        )


class TessieChargePortEntity(TessieEntity, CoverEntity):
    """Cover entity for the charge port."""

    _attr_device_class = CoverDeviceClass.DOOR
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    def __init__(self, vehicle: TessieVehicleData) -> None:
        """Initialize the sensor."""
        super().__init__(vehicle, "charge_state_charge_port_door_open")

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        return not self._value

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open windows."""
        await self.run(open_unlock_charge_port)
        self.set((self.key, True))

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close windows."""
        await self.run(close_charge_port)
        self.set((self.key, False))


class TessieFrontTrunkEntity(TessieEntity, CoverEntity):
    """Cover entity for the charge port."""

    _attr_device_class = CoverDeviceClass.DOOR
    _attr_supported_features = CoverEntityFeature.OPEN

    def __init__(self, vehicle: TessieVehicleData) -> None:
        """Initialize the sensor."""
        super().__init__(vehicle, "vehicle_state_ft")

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        return self._value == TessieCoverStates.CLOSED

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open front trunk."""
        await self.run(open_front_trunk)
        self.set((self.key, TessieCoverStates.OPEN))


class TessieRearTrunkEntity(TessieEntity, CoverEntity):
    """Cover entity for the charge port."""

    _attr_device_class = CoverDeviceClass.DOOR
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    def __init__(self, vehicle: TessieVehicleData) -> None:
        """Initialize the sensor."""
        super().__init__(vehicle, "vehicle_state_rt")

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        return self._value == TessieCoverStates.CLOSED

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open rear trunk."""
        if self.is_closed:
            await self.run(open_close_rear_trunk)
            self.set((self.key, TessieCoverStates.OPEN))

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close rear trunk."""
        if not self.is_closed:
            await self.run(open_close_rear_trunk)
            self.set((self.key, TessieCoverStates.CLOSED))


class TessieSunroofEntity(TessieEntity, CoverEntity):
    """Cover entity for the sunroof."""

    _attr_device_class = CoverDeviceClass.WINDOW
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    def __init__(self, vehicle: TessieVehicleData) -> None:
        """Initialize the sensor."""
        super().__init__(vehicle, "vehicle_state_sun_roof_state")

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        return self._value == TessieCoverStates.CLOSED

    @property
    def current_cover_position(self) -> bool | None:
        """Return the percentage open."""
        return self.get("vehicle_state_sun_roof_percent_open")

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open sunroof."""
        await self.run(vent_sunroof)
        self.set((self.key, TessieCoverStates.OPEN))

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close sunroof."""
        await self.run(close_sunroof)
        self.set((self.key, TessieCoverStates.CLOSED))
