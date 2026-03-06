"""An abstract class common to all Imou entities."""

from __future__ import annotations

from pyimouapi.ha_device import ImouHaDevice

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ImouDataUpdateCoordinator


class ImouEntity(CoordinatorEntity[ImouDataUpdateCoordinator]):
    """Base class for all Imou entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ImouDataUpdateCoordinator,
        entity_type: str,
        device: ImouHaDevice,
    ) -> None:
        """Initialize the Imou entity."""
        super().__init__(coordinator)
        self._entity_type = entity_type
        self._device = device
        self._attr_unique_id = (
            f"{device.device_id}_{device.channel_id or device.product_id}${entity_type}"
        )
        self._attr_translation_key = entity_type
        self._attr_device_info = DeviceInfo(
            identifiers={
                # The combination of DeviceId and ChannelId uniquely identifies the device.
                (
                    DOMAIN,
                    f"{device.device_id}_{device.channel_id or device.product_id}",
                )
            },
            name=device.channel_name or device.device_name,
            manufacturer=device.manufacturer,
            model=device.model,
            sw_version=device.swversion,
            serial_number=device.device_id,
        )
