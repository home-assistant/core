"""Platform for shared base classes for sensors."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import override

from pyintelliclima import (
    FanState,
    IntelliClimaAPI,
    IntelliClimaC800,
    IntelliClimaDevices,
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


@dataclass(frozen=True, kw_only=True)
class IntelliClimaECODescription:
    """Model metadata and access to a device family's current data and API."""

    model: str
    devices_fn: Callable[[IntelliClimaDevices], Mapping[str, IntelliClimaECODevice]]
    api_fn: Callable[
        [IntelliClimaAPI], IntelliClimaEcocomfort2API | IntelliClimaEcocomfort3API
    ]


ECO_DESCRIPTIONS: dict[type[IntelliClimaECODevice], IntelliClimaECODescription] = {
    IntelliClimaECO2: IntelliClimaECODescription(
        model="ECOCOMFORT 2.0",
        devices_fn=lambda data: data.ecocomfort2_devices,
        api_fn=lambda api: api.ecocomfort2,
    ),
    IntelliClimaECO3: IntelliClimaECODescription(
        model="ECOCOMFORT 3",
        devices_fn=lambda data: data.ecocomfort3_devices,
        api_fn=lambda api: api.ecocomfort3,
    ),
}


def eco_device_info(device: IntelliClimaECODevice) -> DeviceInfo:
    """Return the device info shared by all ECOCOMFORT entities."""
    return DeviceInfo(
        identifiers={(DOMAIN, device.id)},
        manufacturer="Fantini Cosmi",
        name=device.name,
        serial_number=device.crono_sn,
        model=ECO_DESCRIPTIONS[type(device)].model,
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
        self._device_description = ECO_DESCRIPTIONS[type(device)]

    @property
    def _devices(self) -> Mapping[str, IntelliClimaECODevice]:
        """Return this family's devices from the latest coordinator update."""
        return self._device_description.devices_fn(self.coordinator.data)

    @property
    def _device_data(self) -> IntelliClimaECODevice:
        return self._devices[self._device_id]

    @property
    def _device_api(self) -> IntelliClimaEcocomfort2API | IntelliClimaEcocomfort3API:
        """Return the API client for this device family."""
        return self._device_description.api_fn(self.coordinator.api)

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
        return super().available and self._device_id in self._devices
