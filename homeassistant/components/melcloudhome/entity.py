"""Base entities for MELCloud Home."""

from aiomelcloudhome import ATAUnit, ATWUnit

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MelCloudHomeCoordinator


class MelCloudHomeEntity(CoordinatorEntity[MelCloudHomeCoordinator]):
    """Base entity for MELCloud Home."""

    _attr_has_entity_name = True
    _attr_name: str | None = None


class MelCloudHomeATAUnitEntity(MelCloudHomeEntity):
    """Base entity for a MELCloud Home Air-to-Air unit."""

    def __init__(self, coordinator: MelCloudHomeCoordinator, unit: ATAUnit) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._unit_id = unit.id
        self._attr_unique_id = unit.id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unit.id)},
            name=unit.name,
            manufacturer="Mitsubishi Electric",
        )

    @property
    def unit(self) -> ATAUnit | None:
        """Return the current unit state from coordinator data."""
        for building in self.coordinator.data.buildings:
            for unit in building.air_to_air_units:
                if unit.id == self._unit_id:
                    return unit
        return None


class MelCloudHomeATWUnitEntity(MelCloudHomeEntity):
    """Base entity for a MELCloud Home Air-to-Water unit."""

    def __init__(self, coordinator: MelCloudHomeCoordinator, unit: ATWUnit) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._unit_id = unit.id
        self._attr_unique_id = unit.id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unit.id)},
            name=unit.name,
            manufacturer="Mitsubishi Electric",
        )

    @property
    def unit(self) -> ATWUnit | None:
        """Return the current unit state from coordinator data."""
        for building in self.coordinator.data.buildings:
            for unit in building.air_to_water_units:
                if unit.id == self._unit_id:
                    return unit
        return None


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
