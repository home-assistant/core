"""Tesla Fleet parent entity class."""

from abc import abstractmethod
from typing import Any

from tesla_fleet_api import EnergySpecific, VehicleSpecific

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    TeslaFleetEnergySiteInfoCoordinator,
    TeslaFleetEnergySiteLiveCoordinator,
    TeslaFleetVehicleDataCoordinator,
)
from .models import TeslaFleetEnergyData, TeslaFleetVehicleData


class TeslaFleetEntity(
    CoordinatorEntity[
        TeslaFleetVehicleDataCoordinator
        | TeslaFleetEnergySiteLiveCoordinator
        | TeslaFleetEnergySiteInfoCoordinator
    ]
):
    """Parent class for all TeslaFleet entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TeslaFleetVehicleDataCoordinator
        | TeslaFleetEnergySiteLiveCoordinator
        | TeslaFleetEnergySiteInfoCoordinator,
        api: VehicleSpecific | EnergySpecific,
        key: str,
    ) -> None:
        """Initialize common aspects of a TeslaFleet entity."""
        super().__init__(coordinator)
        self.api = api
        self.key = key
        self._attr_translation_key = self.key
        self._async_update_attrs()

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        return self.coordinator.last_update_success and self._attr_available

    @property
    def _value(self) -> Any | None:
        """Return a specific value from coordinator data."""
        return self.coordinator.data.get(self.key)

    def get(self, key: str, default: Any | None = None) -> Any | None:
        """Return a specific value from coordinator data."""
        return self.coordinator.data.get(key, default)

    @property
    def is_none(self) -> bool:
        """Return if the value is a literal None."""
        return self.get(self.key, False) is None

    @property
    def has(self) -> bool:
        """Return True if a specific value is in coordinator data."""
        return self.key in self.coordinator.data

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        self.async_write_ha_state()

    @abstractmethod
    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""


class TeslaFleetVehicleEntity(TeslaFleetEntity):
    """Parent class for TeslaFleet Vehicle entities."""

    _last_update: int = 0

    def __init__(
        self,
        data: TeslaFleetVehicleData,
        key: str,
    ) -> None:
        """Initialize common aspects of a Tesla Fleet entity."""

        self._attr_unique_id = f"{data.vin}-{key}"
        self.vehicle = data

        self._attr_device_info = data.device
        super().__init__(data.coordinator, data.api, key)

    @property
    def _value(self) -> Any | None:
        """Return a specific value from coordinator data."""
        return self.coordinator.data.get(self.key)


class TeslaFleetEnergyLiveEntity(TeslaFleetEntity):
    """Parent class for TeslaFleet Energy Site Live entities."""

    def __init__(
        self,
        data: TeslaFleetEnergyData,
        key: str,
    ) -> None:
        """Initialize common aspects of a Tesla Fleet Energy Site Live entity."""
        self._attr_unique_id = f"{data.id}-{key}"
        self._attr_device_info = data.device

        super().__init__(data.live_coordinator, data.api, key)


class TeslaFleetEnergyInfoEntity(TeslaFleetEntity):
    """Parent class for TeslaFleet Energy Site Info entities."""

    def __init__(
        self,
        data: TeslaFleetEnergyData,
        key: str,
    ) -> None:
        """Initialize common aspects of a Tesla Fleet Energy Site Info entity."""
        self._attr_unique_id = f"{data.id}-{key}"
        self._attr_device_info = data.device

        super().__init__(data.info_coordinator, data.api, key)


class TeslaFleetWallConnectorEntity(
    TeslaFleetEntity, CoordinatorEntity[TeslaFleetEnergySiteLiveCoordinator]
):
    """Parent class for Tesla Fleet Wall Connector entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        data: TeslaFleetEnergyData,
        din: str,
        key: str,
    ) -> None:
        """Initialize common aspects of a Tesla Fleet entity."""
        self.din = din
        self._attr_unique_id = f"{data.id}-{din}-{key}"

        # Find the model from the info coordinator
        model: str | None = None
        for wc in data.info_coordinator.data.get("components_wall_connectors", []):
            if wc["din"] == din:
                model = wc.get("part_name")
                break

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, din)},
            manufacturer="Tesla",
            name="Wall Connector",
            via_device=(DOMAIN, str(data.id)),
            serial_number=din.split("-")[-1],
            model=model,
        )

        super().__init__(data.live_coordinator, data.api, key)

    @property
    def _value(self) -> int:
        """Return a specific wall connector value from coordinator data."""
        return (
            self.coordinator.data.get("wall_connectors", {})
            .get(self.din, {})
            .get(self.key)
        )
