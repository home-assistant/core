"""Defines a base Alexa Devices entity."""

from aioamazondevices.structures import AmazonDevice

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import AmazonDevicesCoordinator


class AmazonEntity(CoordinatorEntity[AmazonDevicesCoordinator]):
    """Defines a base Alexa Devices entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AmazonDevicesCoordinator,
        serial_num: str,
        description: EntityDescription,
        connect_to_hub: bool = False,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._serial_num = serial_num
        if connect_to_hub:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, service_device_id(coordinator))},
                manufacturer="Amazon",
                name=coordinator.config_entry.title,
                entry_type=DeviceEntryType.SERVICE,
            )
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, serial_num)},
                name=self.device.account_name,
                model=self.device.model,
                model_id=self.device.device_type,
                manufacturer=self.device.manufacturer or "Amazon",
                hw_version=self.device.hardware_version,
                sw_version=self.device.software_version,
                serial_number=serial_num,
                via_device=(DOMAIN, service_device_id(coordinator)),
            )
        self.entity_description = description
        self._attr_unique_id = f"{serial_num}-{description.key}"

    @property
    def device(self) -> AmazonDevice:
        """Return the device."""
        return self.coordinator.data[self._serial_num]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self._serial_num in self.coordinator.data
            and self.device.online
        )


def service_device_id(coordinator: AmazonDevicesCoordinator) -> str:
    """Return service device id."""
    return slugify(f"{coordinator.config_entry.title}_service_device")
