"""Entities for the ViCare integration."""
from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareFuelCell import FuelCellBurner
from PyViCare.PyViCareGazBoiler import GazBurner
from PyViCare.PyViCareHeatingDevice import (
    HeatingCircuit,
    HeatingDeviceWithComponent as PyViCareHeatingDeviceComponent,
)
from PyViCare.PyViCareHeatPump import Compressor
from PyViCare.PyViCareOilBoiler import OilBurner

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class ViCareEntity(Entity):
    """Base class for ViCare entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device_config: PyViCareDeviceConfig,
        device: PyViCareDevice | PyViCareHeatingDeviceComponent,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the entity."""
        self._api = device

        self._attr_unique_id = f"{device_config.getConfig().serial}-{unique_id_suffix}"
        # valid for compressors, circuits, burners (HeatingDeviceWithComponent)
        if hasattr(device, "id"):
            self._attr_unique_id += f"-{device.id}"

        if isinstance(device, HeatingCircuit):
            self._attr_device_info = self._get_info_for_component(
                device_config, device, "Circuit"
            )
        elif isinstance(device, FuelCellBurner | GazBurner | OilBurner):
            self._attr_device_info = self._get_info_for_component(
                device_config, device, "Burner"
            )
        elif isinstance(device, Compressor):
            self._attr_device_info = self._get_info_for_component(
                device_config, device, "Compressor"
            )
        else:
            self._attr_device_info = self._get_info_for_device(device_config)

    def _get_info_for_component(
        self,
        device_config: PyViCareDeviceConfig,
        device: PyViCareDevice,
        component_type: str,
    ) -> DeviceInfo:
        return DeviceInfo(
            via_device=(DOMAIN, device_config.getConfig().serial),
            identifiers={
                (
                    DOMAIN,
                    f"{device_config.getConfig().serial}-{component_type.lower()}-{device.id}",
                )
            },
            name=f"{component_type}",
            manufacturer="Viessmann",
            configuration_url="https://developer.viessmann.com/",
        )

    def _get_info_for_device(self, device_config: PyViCareDeviceConfig) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, device_config.getConfig().serial)},
            serial_number=device_config.getConfig().serial,
            name=device_config.getModel(),
            manufacturer="Viessmann",
            model=device_config.getModel(),
            configuration_url="https://developer.viessmann.com/",
        )
