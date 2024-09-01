"""Aquacell entity."""

from aioaquacell import Softener

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AquacellCoordinator


class AquacellEntity(CoordinatorEntity[AquacellCoordinator]):
    """Representation of an aquacell entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AquacellCoordinator,
        softener_key: str,
        entity_key: str,
    ) -> None:
        """Initialize the aquacell entity."""
        super().__init__(coordinator)

        self.softener_key = softener_key

        self._attr_unique_id = f"{softener_key}-{entity_key}"
        self._attr_device_info = DeviceInfo(
            name=self.softener.name,
            hw_version=self.softener.fwVersion,
            identifiers={(DOMAIN, str(softener_key))},
            manufacturer=self.softener.brand,
            model=self.softener.ssn,
            serial_number=softener_key,
        )

    @property
    def softener(self) -> Softener:
        """Handle updated data from the coordinator."""
        return self.coordinator.data[self.softener_key]
