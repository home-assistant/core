"""Provide a common entity class for myUplink entities."""
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MyUplinkDataCoordinator


class MyUplinkEntity(CoordinatorEntity[MyUplinkDataCoordinator]):
    """Representation of a sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MyUplinkDataCoordinator,
        device_id: str,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator)

        # Internal properties
        self.device_id = device_id

        # Basic values
        self._attr_unique_id = f"{device_id}-{unique_id_suffix}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)})
