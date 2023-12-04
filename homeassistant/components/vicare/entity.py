"""Entities for the ViCare integration."""
from typing import Final

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareHeatingDevice import (
    HeatingCircuit as PyViCareHeatingCircuit,
    HeatingDeviceWithComponent as PyViCareHeatingDevicWithComponent,
)

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

MANUFACTURER: Final = "Viessmann"
DEVELOPER_PORTAL: Final = "https://app.developer.viessmann.com/"


class ViCareEntity(Entity):
    """Base class for ViCare entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device_config: PyViCareDeviceConfig,
        device: PyViCareDevice | PyViCareHeatingDevicWithComponent,
        unique_id_suffix: str,
        custom_device_name: str | None = None,
    ) -> None:
        """Initialize the entity."""
        self._api = device

        self._attr_unique_id = f"{device_config.getConfig().serial}-{unique_id_suffix}"
        # valid for compressors, circuits, burners (HeatingDeviceWithComponent)
        if hasattr(device, "id"):
            self._attr_unique_id += f"-{device.id}"

        if isinstance(device, PyViCareHeatingCircuit):
            self._attr_device_info = self._get_info_for_heating_circuit(
                device_config, device, custom_device_name
            )
        else:
            self._attr_device_info = self._get_info_for_device(device_config)

    def _get_info_for_heating_circuit(
        self,
        device_config: PyViCareDeviceConfig,
        device: PyViCareDevice,
        custom_device_name: str | None,
    ) -> DeviceInfo:
        component_type = "Heating Circuit"
        return DeviceInfo(
            via_device=(DOMAIN, device_config.getConfig().serial),
            identifiers={
                (
                    DOMAIN,
                    f"{device_config.getConfig().serial}-{component_type.lower().replace(' ', '_')}-{device.id}",
                )
            },
            name=component_type if custom_device_name is None else custom_device_name,
            model=component_type,
            manufacturer=MANUFACTURER,
            configuration_url=DEVELOPER_PORTAL,
        )

    def _get_info_for_device(self, device_config: PyViCareDeviceConfig) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, device_config.getConfig().serial)},
            serial_number=device_config.getConfig().serial,
            name=device_config.getModel(),
            model=device_config.getModel(),
            manufacturer=MANUFACTURER,
            configuration_url=DEVELOPER_PORTAL,
        )
