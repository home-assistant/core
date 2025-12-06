"""Platform for shared base classes for sensors."""

from pyintelliclima.intelliclima_types import IntelliClimaC800, IntelliClimaECO

from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
)
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IntelliClimaCoordinator


class IntelliClimaEntity(CoordinatorEntity[IntelliClimaCoordinator]):
    """Define a generic class for IntelliClima entities."""

    _attr_attribution = "Data provided by unpublished IntelliClima API"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IntelliClimaCoordinator,
        device: IntelliClimaECO | IntelliClimaC800,
        description: EntityDescription,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator=coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{device.id}_{description.key}"

        # Make this HA "device" use the IntelliClima device name.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            manufacturer="Fantini Cosmi",
            name=device.name,
            serial_number=device.crono_sn,
        )

        self._device_id = device.id
        self._device_sn = device.crono_sn


class IntelliClimaECOEntity(IntelliClimaEntity):
    """Specific entity for the ECOCOMFORT 2.0."""

    def __init__(
        self,
        coordinator: IntelliClimaCoordinator,
        device: IntelliClimaECO,
        description: EntityDescription,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator, device, description)

        self._attr_device_info = self._build_device_info(device)

    def _build_device_info(self, device: IntelliClimaECO) -> DeviceInfo:
        info: DeviceInfo = self.device_info or DeviceInfo()

        info["model"] = "ECOCOMFORT 2.0"
        info["sw_version"] = device.fw
        info["connections"] = {
            (CONNECTION_BLUETOOTH, device.mac),
            (CONNECTION_NETWORK_MAC, device.macwifi),
        }

        return info

    @property
    def _device_data(self) -> IntelliClimaECO:
        return self.coordinator.data.ecocomfort2_devices[self._device_id]
