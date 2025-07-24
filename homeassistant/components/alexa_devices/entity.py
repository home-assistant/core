"""Defines a base Alexa Devices entity."""

from aioamazondevices.api import AmazonDevice
from aioamazondevices.const import SPEAKER_GROUP_MODEL

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._serial_num = serial_num
        model_details = coordinator.api.get_model_details(self.device) or {}
        model = model_details.get("model")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_num)},
            name=self.device.account_name,
            model=model,
            model_id=self.device.device_type,
            manufacturer=model_details.get("manufacturer", "Amazon"),
            hw_version=model_details.get("hw_version"),
            sw_version=(
                self.device.software_version if model != SPEAKER_GROUP_MODEL else None
            ),
            serial_number=serial_num if model != SPEAKER_GROUP_MODEL else None,
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
