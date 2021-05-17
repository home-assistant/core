"""Base classes for Renault entities."""
from __future__ import annotations

from typing import Any, cast

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


class RenaultDataEntity(CoordinatorEntity, Entity):
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
        return f"{self.vehicle.details.vin}-{self._entity_type}"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Data can succeed, but be empty
        return self.coordinator.last_update_success and self.coordinator.data


class RenaultBatteryDataEntity(RenaultDataEntity):
    """Implementation of a Renault entity with battery coordinator."""

    def __init__(self, vehicle: RenaultVehicleProxy, entity_type: str) -> None:
        """Initialise entity."""
        super().__init__(vehicle, entity_type, "battery")

    @property
    def data(self) -> KamereonVehicleBatteryStatusData:
        """Return collected data."""
        return cast(KamereonVehicleBatteryStatusData, self.coordinator.data)

    @property
    def device_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of this entity."""
        attrs = {}
        if self.data.timestamp:
            attrs[ATTR_LAST_UPDATE] = self.data.timestamp
        return attrs


class RenaultChargeModeDataEntity(RenaultDataEntity):
    """Implementation of a Renault entity with charge_mode coordinator."""

    def __init__(self, vehicle: RenaultVehicleProxy, entity_type: str) -> None:
        """Initialise entity."""
        super().__init__(vehicle, entity_type, "charge_mode")

    @property
    def data(self) -> KamereonVehicleChargeModeData:
        """Return collected data."""
        return cast(KamereonVehicleChargeModeData, self.coordinator.data)


class RenaultCockpitDataEntity(RenaultDataEntity):
    """Implementation of a Renault entity with cockpit coordinator."""

    def __init__(self, vehicle: RenaultVehicleProxy, entity_type: str) -> None:
        """Initialise entity."""
        super().__init__(vehicle, entity_type, "cockpit")

    @property
    def data(self) -> KamereonVehicleCockpitData:
        """Return collected data."""
        return cast(KamereonVehicleCockpitData, self.coordinator.data)


class RenaultHVACDataEntity(RenaultDataEntity):
    """Implementation of a Renault entity with hvac_status coordinator."""

    def __init__(self, vehicle: RenaultVehicleProxy, entity_type: str) -> None:
        """Initialise entity."""
        super().__init__(vehicle, entity_type, "hvac_status")

    @property
    def data(self) -> KamereonVehicleHvacStatusData:
        """Return collected data."""
        return cast(KamereonVehicleHvacStatusData, self.coordinator.data)
