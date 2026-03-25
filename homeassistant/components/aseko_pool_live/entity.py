"""Aseko entity."""

from aioaseko import Unit

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AsekoDataUpdateCoordinator


class AsekoEntity(CoordinatorEntity[AsekoDataUpdateCoordinator]):
    """Representation of an aseko entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        unit: Unit,
        coordinator: AsekoDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the aseko entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._unit = unit
        self._attr_unique_id = f"{self.unit.serial_number}{self.entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.unit.serial_number)},
            serial_number=self.unit.serial_number,
            name=unit.name or unit.serial_number,
            manufacturer=(
                self.unit.brand_name.primary
                if self.unit.brand_name is not None
                else None
            ),
            model=(
                self.unit.brand_name.secondary
                if self.unit.brand_name is not None
                else None
            ),
            configuration_url=f"https://aseko.cloud/unit/{self.unit.serial_number}",
        )

    @property
    def unit(self) -> Unit:
        """Return the aseko unit."""
        return self.coordinator.data[self._unit.serial_number]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.unit.serial_number in self.coordinator.data
            and self.unit.online
        )
