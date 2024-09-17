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
        user_id: str,
        coordinator: AsekoDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the aseko entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._unit = unit
        self._attr_unique_id = (
            f"{user_id}_{self._unit.serial_number}_{self.entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{user_id}_{self._unit.serial_number}")},
            serial_number=self._unit.serial_number,
            name=(
                self._unit.name
                if (self._unit.name is not None and self._unit.name != "")
                else self._unit.serial_number
            ),
            manufacturer=(
                self._unit.brand_name.primary
                if self._unit.brand_name is not None
                else None
            ),
            model=(
                self._unit.brand_name.secondary
                if self._unit.brand_name is not None
                else None
            ),
            configuration_url=f"https://aseko.cloud/unit/{self._unit.serial_number}",
        )

    def _handle_coordinator_update(self) -> None:
        self._unit = self.coordinator.data[self._unit.serial_number]
        return super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._unit.online
