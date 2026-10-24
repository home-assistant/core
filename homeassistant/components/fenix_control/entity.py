"""Base entity for the FENIX Control integration."""

from typing import override

from pyfenixcontrol import Device

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FenixControlCoordinator


class FenixControlEntity(CoordinatorEntity[FenixControlCoordinator]):
    """Base class for FENIX Control entities."""

    _attr_has_entity_name = True
    device: Device

    def __init__(self, coordinator: FenixControlCoordinator, device_id: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        device = self.device = coordinator.data.devices[device_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=" ".join(
                name for name in (device.installation_name, device.name) if name
            )
            or None,
            manufacturer="FENIX",
            model="TFT Wi-Fi",
            model_id=device.model,
            sw_version=device.software_version,
            serial_number=device_id,
        )

    @property
    @override
    def available(self) -> bool:
        """Return if the thermostat is still reported by the cloud."""
        return super().available and self._device_id in self.coordinator.data.devices

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Keep the last known state of a thermostat the cloud stopped reporting."""
        if (device := self.coordinator.data.devices.get(self._device_id)) is not None:
            self.device = device
        super()._handle_coordinator_update()
