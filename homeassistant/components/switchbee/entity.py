"""Support for SwitchBee entity."""
from switchbee import SWITCHBEE_BRAND
from switchbee.device import SwitchBeeBaseDevice

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SwitchBeeCoordinator


class SwitchBeeEntity(CoordinatorEntity[SwitchBeeCoordinator]):
    """Representation of a Switchbee entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device: SwitchBeeBaseDevice,
        coordinator: SwitchBeeCoordinator,
    ) -> None:
        """Initialize the Switchbee entity."""
        super().__init__(coordinator)
        self._device = device
        self._attr_name = device.name
        self._attr_unique_id = f"{coordinator.mac_formated}-{device.id}"


class SwitchBeeDeviceEntity(SwitchBeeEntity):
    """Representation of a Switchbee device entity."""

    def __init__(
        self,
        device: SwitchBeeBaseDevice,
        coordinator: SwitchBeeCoordinator,
    ) -> None:
        """Initialize the Switchbee device."""
        super().__init__(device, coordinator)
        self._attr_device_info = DeviceInfo(
            name=f"SwitchBee {device.unit_id}",
            identifiers={
                (
                    DOMAIN,
                    f"{device.unit_id}-{coordinator.mac_formated}",
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
