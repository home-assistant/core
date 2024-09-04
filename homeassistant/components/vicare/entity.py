"""Entities for the ViCare integration."""

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareHeatingDevice import (
    HeatingDeviceWithComponent as PyViCareHeatingDeviceComponent,
)

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class ViCareEntity(Entity):
    """Base class for ViCare entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        unique_id_suffix: str,
        device_config: PyViCareDeviceConfig,
        device: PyViCareDevice,
        component: PyViCareHeatingDeviceComponent | None = None,
    ) -> None:
        """Initialize the entity."""
        gateway_serial = device_config.getConfig().serial
        device_serial = device.getSerial()
        identifier = f"{gateway_serial}_{device_serial}"

        self._api: PyViCareDevice | PyViCareHeatingDeviceComponent = (
            component if component else device
        )
        self._attr_unique_id = f"{identifier}-{unique_id_suffix}"
        if component:
            self._attr_unique_id += f"-{component.id}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            serial_number=device_serial,
            name=device_config.getModel(),
            manufacturer="Viessmann",
            model=device_config.getModel(),
            configuration_url="https://developer.viessmann.com/",
        )
