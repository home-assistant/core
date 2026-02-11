"""Platform for shared base classes for sensors."""

from pyintelliclima.intelliclima_types import IntelliClimaC800, IntelliClimaECO

from homeassistant.const import ATTR_CONNECTIONS, ATTR_MODEL, ATTR_SW_VERSION
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IntelliClimaCoordinator


class IntelliClimaEntity(CoordinatorEntity[IntelliClimaCoordinator]):
    """Define a generic class for IntelliClima entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IntelliClimaCoordinator,
        device: IntelliClimaECO | IntelliClimaC800,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator=coordinator)

        self._attr_unique_id = device.id

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
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator, device)

        self._attr_device_info: DeviceInfo = self.device_info or DeviceInfo()

        self._attr_device_info[ATTR_MODEL] = "ECOCOMFORT 2.0"
        self._attr_device_info[ATTR_SW_VERSION] = device.fw
        self._attr_device_info[ATTR_CONNECTIONS] = {
            (CONNECTION_BLUETOOTH, device.mac),
            (CONNECTION_NETWORK_MAC, device.macwifi),
        }

    @property
    def _device_data(self) -> IntelliClimaECO:
        return self.coordinator.data.ecocomfort2_devices[self._device_id]

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self._device_id in self.coordinator.data.ecocomfort2_devices
        )
