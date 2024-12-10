"""Defines a base Amazon Devices entity."""

from aioamazondevices import AmazonDevice
from aioamazondevices.const import DEVICE_TYPE_TO_MODEL

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AmazonDevicesCoordinator


class AmazonEntity(CoordinatorEntity[AmazonDevicesCoordinator]):
    """Defines a base Amazon Devices entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AmazonDevicesCoordinator,
        serial_num: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._serial_num = serial_num
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_num)},
            name=self.device.account_name,
            model=DEVICE_TYPE_TO_MODEL.get(self.device.device_type),
            manufacturer="Amazon",
            hw_version=self.device.device_type,
            sw_version=self.device.software_version,
            serial_number=serial_num,
        )

    @property
    def device(self) -> AmazonDevice:
        """Return the device."""
        return self.coordinator.data[self._serial_num]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._serial_num in self.coordinator.data
