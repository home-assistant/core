"""Platform for shared base classes for sensors."""

from typing import override

from pyintelliclima import (
    FanState,
    IntelliClimaC800,
    IntelliClimaECO2,
    IntelliClimaECO3,
    IntelliClimaEcocomfort2API,
    IntelliClimaEcocomfort3API,
)

from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IntelliClimaCoordinator

type IntelliClimaECODevice = IntelliClimaECO2 | IntelliClimaECO3


def eco_device_info(device: IntelliClimaECODevice) -> DeviceInfo:
    """Return the device info shared by all ECOCOMFORT entities."""
    return DeviceInfo(
        identifiers={(DOMAIN, device.id)},
        manufacturer="Fantini Cosmi",
        name=device.name,
        serial_number=device.crono_sn,
        model="ECOCOMFORT 3"
        if isinstance(device, IntelliClimaECO3)
        else "ECOCOMFORT 2.0",
        sw_version=device.fw,
        connections={
            (CONNECTION_BLUETOOTH, device.mac),
            (CONNECTION_NETWORK_MAC, device.macwifi),
        },
    )


class IntelliClimaEntity(CoordinatorEntity[IntelliClimaCoordinator]):
    """Define a generic class for IntelliClima entities."""

    _attr_has_entity_name = True
    _attr_device_info: DeviceInfo

    def __init__(
        self,
        coordinator: IntelliClimaCoordinator,
        device: IntelliClimaECODevice | IntelliClimaC800,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator=coordinator)

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
    """Specific entity for an ECOCOMFORT device."""

    def __init__(
        self,
        coordinator: IntelliClimaCoordinator,
        device: IntelliClimaECODevice,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator, device)

        self._attr_device_info = eco_device_info(device)
        self._is_ecocomfort3 = isinstance(device, IntelliClimaECO3)

    @property
    def _device_data(self) -> IntelliClimaECODevice:
        if self._is_ecocomfort3:
            return self.coordinator.data.ecocomfort3_devices[self._device_id]
        return self.coordinator.data.ecocomfort2_devices[self._device_id]

    @property
    def _device_api(self) -> IntelliClimaEcocomfort2API | IntelliClimaEcocomfort3API:
        """Return the API client for this device family."""
        if self._is_ecocomfort3:
            return self.coordinator.api.ecocomfort3
        return self.coordinator.api.ecocomfort2

    @property
    def _fan_state(self) -> FanState | None:
        """Return the running state, or None if the device reports an undefined one."""
        try:
            return self._device_data.fan_state
        except ValueError:
            return None

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        devices = (
            self.coordinator.data.ecocomfort3_devices
            if self._is_ecocomfort3
            else self.coordinator.data.ecocomfort2_devices
        )
        return super().available and self._device_id in devices
