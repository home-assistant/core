"""Aquacell entity."""
from aioaquacell import Softener

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AquacellCoordinator


class AquacellEntity(CoordinatorEntity[AquacellCoordinator]):
    """Representation of an aquacell entity."""

    _attr_has_entity_name = True
    _attr_available = True

    def __init__(self, softener: Softener, coordinator: AquacellCoordinator) -> None:
        """Initialize the aquacell entity."""
        super().__init__(coordinator)

        self._device_model = softener.dsn
        self._device_name = softener.name

        self._attr_device_info = DeviceInfo(
            name=self._device_name,
            identifiers={(DOMAIN, str(softener.ssn))},
            manufacturer=softener.brand,
            model=self._device_model,
        )
