"""Aseko entity."""
from aioaseko import Unit

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AsekoDataUpdateCoordinator


class AsekoEntity(CoordinatorEntity[AsekoDataUpdateCoordinator]):
    """Representation of an aseko entity."""

    def __init__(self, unit: Unit, coordinator: AsekoDataUpdateCoordinator) -> None:
        """Initialize the aseko entity."""
        super().__init__(coordinator)
        self._unit = unit

        self._device_model = f"ASIN AQUA {self._unit.type}"
        self._device_name = self._unit.name if self._unit.name else self._device_model

        self._attr_device_info = DeviceInfo(
            name=self._device_name,
            identifiers={(DOMAIN, str(self._unit.serial_number))},
            manufacturer="Aseko",
            model=self._device_model,
        )
