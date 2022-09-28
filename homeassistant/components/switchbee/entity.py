"""Support for SwitchBee entity."""
from typing import Generic, TypeVar

from switchbee import SWITCHBEE_BRAND
from switchbee.device import SwitchBeeBaseDevice

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SwitchBeeCoordinator

_DeviceTypeT = TypeVar("_DeviceTypeT", bound=SwitchBeeBaseDevice)


class SwitchBeeEntity(CoordinatorEntity[SwitchBeeCoordinator], Generic[_DeviceTypeT]):
    """Representation of a Switchbee entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device: _DeviceTypeT,
        coordinator: SwitchBeeCoordinator,
    ) -> None:
        """Initialize the Switchbee entity."""
        super().__init__(coordinator)
        self._device = device
        self._attr_name = device.name
        self._attr_unique_id = f"{coordinator.mac_formatted}-{device.id}"


class SwitchBeeDeviceEntity(SwitchBeeEntity[_DeviceTypeT]):
    """Representation of a Switchbee device entity."""

    def __init__(
        self,
        device: _DeviceTypeT,
        coordinator: SwitchBeeCoordinator,
    ) -> None:
        """Initialize the Switchbee device."""
        super().__init__(device, coordinator)
        self._attr_device_info = DeviceInfo(
            name=f"SwitchBee {device.unit_id}",
            identifiers={
                (
                    DOMAIN,
                    f"{device.unit_id}-{coordinator.mac_formatted}",
                )
            },
            manufacturer=SWITCHBEE_BRAND,
            model=coordinator.api.module_display(device.unit_id),
            suggested_area=device.zone,
            via_device=(
                DOMAIN,
                f"{coordinator.api.name} ({coordinator.api.mac})",
            ),
        )
