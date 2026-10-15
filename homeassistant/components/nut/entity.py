"""Base entity for the NUT integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PyNUTData
from .const import DOMAIN
from .coordinator import NutCoordinator


class NUTBaseEntity(CoordinatorEntity[NutCoordinator]):
    """NUT base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NutCoordinator,
        entity_description: EntityDescription,
        data: PyNUTData,
        unique_id: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self.entity_description = entity_description
        self._attr_unique_id = f"{unique_id}_{entity_description.key}"

        self.pynut_data = data
        device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=self.pynut_data.device_name,
        )
        nut_device_info = data.device_info
        if nut_device_info.manufacturer is not None:
            device_info.manufacturer = nut_device_info.manufacturer
        if nut_device_info.model is not None:
            device_info.model = nut_device_info.model
        if nut_device_info.firmware is not None:
            device_info.sw_version = nut_device_info.firmware
        if nut_device_info.serial is not None:
            device_info.serial_number = nut_device_info.serial
        self._attr_device_info = device_info
