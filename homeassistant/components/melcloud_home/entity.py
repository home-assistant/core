"""Base entities for MELCloud Home."""

from abc import abstractmethod
from typing import override

from aiomelcloudhome import ATAUnit, ATWUnit
from yarl import URL

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_ATA, DEVICE_ATW, DOMAIN, WEB_BASE_URL
from .coordinator import MelCloudHomeCoordinator


class MelCloudHomeEntity(CoordinatorEntity[MelCloudHomeCoordinator]):
    """Base entity for MELCloud Home."""

    _attr_has_entity_name = True


class MelCloudHomeUnitEntity[_UnitT: (ATAUnit, ATWUnit)](MelCloudHomeEntity):
    """Base entity for a MELCloud Home unit."""

    _unit_type_path: str

    def __init__(self, coordinator: MelCloudHomeCoordinator, unit: _UnitT) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._unit_id = unit.id
        self._attr_unique_id = unit.id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unit.id)},
            name=unit.name,
            manufacturer="Mitsubishi Electric",
            configuration_url=URL(
                f"{WEB_BASE_URL}/{self._unit_type_path}/{unit.id}/temperature"
            ),
        )

    @abstractmethod
    def _units_dict(self) -> dict[str, _UnitT]:
        """Return the coordinator's units dict keyed by id."""

    @property
    @override
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and self._unit_id in self._units_dict()

    @property
    def unit(self) -> _UnitT:
        """Return the current unit state from coordinator data."""
        return self._units_dict()[self._unit_id]


class MelCloudHomeATAUnitEntity(MelCloudHomeUnitEntity[ATAUnit]):
    """Base entity for a MELCloud Home Air-to-Air unit."""

    _unit_type_path = DEVICE_ATA

    @override
    def _units_dict(self) -> dict[str, ATAUnit]:
        """Return ATA units dict from coordinator."""
        return self.coordinator.ata_units


class MelCloudHomeATWUnitEntity(MelCloudHomeUnitEntity[ATWUnit]):
    """Base entity for a MELCloud Home Air-to-Water unit."""

    _unit_type_path = DEVICE_ATW

    @override
    def _units_dict(self) -> dict[str, ATWUnit]:
        """Return ATW units dict from coordinator."""
        return self.coordinator.atw_units


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
