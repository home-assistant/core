"""Entities for the ViCare integration."""
from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class ViCareEntity(Entity):
    """Base class for ViCare entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device_config: PyViCareDeviceConfig,
        device: PyViCareDevice,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the entity."""
        self._api = device

        self._attr_unique_id = f"{device_config.getConfig().serial}-{unique_id_suffix}"
        # valid for compressors, circuits, burners (HeatingDeviceWithComponent)
        if hasattr(device, "id"):
            self._attr_unique_id += f"-{device.id}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_config.getConfig().serial)},
            serial_number=device_config.getConfig().serial,
            name=device_config.getModel(),
            manufacturer="Viessmann",
            model=device_config.getModel(),
            configuration_url="https://developer.viessmann.com/",
        )
