"""Base classes for Renault entities."""
from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from renault_api.kamereon.enums import ChargeState, PlugState
from renault_api.kamereon.models import (
    KamereonVehicleBatteryStatusData,
    KamereonVehicleChargeModeData,
    KamereonVehicleCockpitData,
    KamereonVehicleHvacStatusData,
)

from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .renault_vehicle import RenaultVehicleProxy

ATTR_LAST_UPDATE = "last_update"

T = TypeVar("T")


class RenaultDataEntity(Generic[T], CoordinatorEntity[Optional[T]], Entity):
    """Implementation of a Renault entity with a data coordinator."""

    def __init__(
        self, vehicle: RenaultVehicleProxy, entity_type: str, coordinator_key: str
    ) -> None:
        """Initialise entity."""
        super().__init__(vehicle.coordinators[coordinator_key])
        self.vehicle = vehicle
        self._entity_type = entity_type

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return self.vehicle.device_info

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this entity."""
        return slugify(f"{self.vehicle.details.vin}-{self._entity_type}")

    @property
    def name(self) -> str:
        """Return the name of this entity."""
        return self._entity_type

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Data can succeed, but be empty
        return super().available and self.coordinator.data is not None

    @property
    def data(self) -> T | None:
        """Return collected data."""
        return self.coordinator.data


class RenaultBatteryDataEntity(RenaultDataEntity[KamereonVehicleBatteryStatusData]):
    """Implementation of a Renault entity with battery coordinator."""

    def __init__(self, vehicle: RenaultVehicleProxy, entity_type: str) -> None:
        """Initialise entity."""
        super().__init__(vehicle, entity_type, "battery")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of this entity."""
        if self.data is None:
            return {ATTR_LAST_UPDATE: None}
        return {ATTR_LAST_UPDATE: self.data.timestamp}

    @property
    def is_charging(self) -> bool:
        """Return charge state as boolean."""
        return (
            self.data is not None
            and self.data.get_charging_status() == ChargeState.CHARGE_IN_PROGRESS
        )

    @property
    def is_plugged_in(self) -> bool:
        """Return plug state as boolean."""
        return (
            self.data is not None and self.data.get_plug_status() == PlugState.PLUGGED
        )


class RenaultChargeModeDataEntity(RenaultDataEntity[KamereonVehicleChargeModeData]):
    """Implementation of a Renault entity with charge_mode coordinator."""

    def __init__(self, vehicle: RenaultVehicleProxy, entity_type: str) -> None:
        """Initialise entity."""
        super().__init__(vehicle, entity_type, "charge_mode")


class RenaultCockpitDataEntity(RenaultDataEntity[KamereonVehicleCockpitData]):
    """Implementation of a Renault entity with cockpit coordinator."""

    def __init__(self, vehicle: RenaultVehicleProxy, entity_type: str) -> None:
        """Initialise entity."""
        super().__init__(vehicle, entity_type, "cockpit")


class RenaultHVACDataEntity(RenaultDataEntity[KamereonVehicleHvacStatusData]):
    """Implementation of a Renault entity with hvac_status coordinator."""

    def __init__(self, vehicle: RenaultVehicleProxy, entity_type: str) -> None:
        """Initialise entity."""
        super().__init__(vehicle, entity_type, "hvac_status")
