"""Shared entity base — device_info and the coordinator plumbing."""

from typing import override

from sofar_modbus.modern.device import SofarInverter

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_MANUFACTURER, DOMAIN
from .coordinator import SofarDataUpdateCoordinator, SofarRuntimeData


def build_device_info(device: SofarInverter) -> DeviceInfo:
    """The one physical inverter every entity on this config entry belongs to."""
    serial = device.serial_number
    assert serial is not None
    return DeviceInfo(
        identifiers={(DOMAIN, serial)},
        manufacturer=ATTR_MANUFACTURER,
        model=device.model or None,
        serial_number=serial,
    )


class SofarEntity(CoordinatorEntity[SofarDataUpdateCoordinator]):
    """Base for every Sofar entity — one physical inverter per config entry."""

    _attr_has_entity_name = True

    def __init__(
        self,
        runtime_data: SofarRuntimeData,
        unique_id_suffix: str,
        component: str,
    ) -> None:
        """Initialize the entity, bound to whichever coordinator serves it."""
        super().__init__(runtime_data.coordinator_for(component))
        serial = self.coordinator.device.serial_number
        assert serial is not None
        self._component = component
        self._attr_unique_id = f"{serial}_{unique_id_suffix}"
        self._attr_device_info = build_device_info(self.coordinator.device)

    @property
    @override
    def available(self) -> bool:
        """Whether this entity's component answered the most recent poll."""
        if not super().available:
            return False
        report = self.coordinator.data
        return report is None or self._component not in report.failed
