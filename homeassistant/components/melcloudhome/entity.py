"""Base entities for MELCloud Home."""

from abc import abstractmethod

from aiomelcloudhome import ATAUnit, ATWUnit, Building

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MelCloudHomeCoordinator


class MelCloudHomeEntity(CoordinatorEntity[MelCloudHomeCoordinator]):
    """Base entity for MELCloud Home."""

    _attr_has_entity_name = True
    _attr_name: str | None = None


class MelCloudHomeUnitEntity[_UnitT: (ATAUnit, ATWUnit)](MelCloudHomeEntity):
    """Base entity for a MELCloud Home unit."""

    def __init__(self, coordinator: MelCloudHomeCoordinator, unit: _UnitT) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._unit_id = unit.id
        self._attr_unique_id = unit.id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unit.id)},
            name=unit.name,
            manufacturer="Mitsubishi Electric",
        )

    @abstractmethod
    def _units_for_building(self, building: Building) -> list[_UnitT]:
        """Return the list of units from a building."""

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and any(
            unit.id == self._unit_id
            for building in self.coordinator.data.buildings
            for unit in self._units_for_building(building)
        )

    @property
    def unit(self) -> _UnitT:
        """Return the current unit state from coordinator data."""
        return next(
            unit
            for building in self.coordinator.data.buildings
            for unit in self._units_for_building(building)
            if unit.id == self._unit_id
        )


class MelCloudHomeATAUnitEntity(MelCloudHomeUnitEntity[ATAUnit]):
    """Base entity for a MELCloud Home Air-to-Air unit."""

    def _units_for_building(self, building: Building) -> list[ATAUnit]:
        """Return ATA units from a building."""
        return building.air_to_air_units


class MelCloudHomeATWUnitEntity(MelCloudHomeUnitEntity[ATWUnit]):
    """Base entity for a MELCloud Home Air-to-Water unit."""

    def _units_for_building(self, building: Building) -> list[ATWUnit]:
        """Return ATW units from a building."""
        return building.air_to_water_units


class MelCloudHomeATWZoneEntity(MelCloudHomeATWUnitEntity):
    """Base entity for an ATW zone entity."""

    def __init__(
        self,
        coordinator: MelCloudHomeCoordinator,
        unit: ATWUnit,
        zone_number: int,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, unit)
        self._zone_number = zone_number
        self._attr_unique_id = f"{unit.id}_zone_{zone_number}"
        self._attr_name = f"Zone {zone_number}"

    @property
    def zone_number(self) -> int:
        """Return the zone number."""
        return self._zone_number


class MelCloudHomeATWTankEntity(MelCloudHomeATWUnitEntity):
    """Base entity for the ATW tank/DHW entity."""

    def __init__(self, coordinator: MelCloudHomeCoordinator, unit: ATWUnit) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, unit)
        self._attr_unique_id = f"{unit.id}_tank"
        self._attr_name = "Hot water"
