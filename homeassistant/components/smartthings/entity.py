"""Support for SmartThings Cloud."""

from __future__ import annotations

from pysmartthings.device import DeviceEntity

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, SIGNAL_SMARTTHINGS_UPDATE


class SmartThingsEntity(Entity):
    """Defines a SmartThings entity."""

    _attr_should_poll = False

    def __init__(self, device: DeviceEntity) -> None:
        """Initialize the instance."""
        self._device = device
        self._dispatcher_remove = None
        self._attr_name = device.label
        self._attr_unique_id = device.device_id
        self._attr_device_info = DeviceInfo(
            configuration_url="https://account.smartthings.com",
            identifiers={(DOMAIN, device.device_id)},
            manufacturer=device.status.ocf_manufacturer_name,
            model=device.status.ocf_model_number,
            name=device.label,
            hw_version=device.status.ocf_hardware_version,
            sw_version=device.status.ocf_firmware_version,
        )

    async def async_added_to_hass(self):
        """Device added to hass."""

        async def async_update_state(devices):
            """Update device state."""
            if self._device.device_id in devices:
                await self.async_update_ha_state(True)

        self._dispatcher_remove = async_dispatcher_connect(
            self.hass, SIGNAL_SMARTTHINGS_UPDATE, async_update_state
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect the device when removed."""
        if self._dispatcher_remove:
            self._dispatcher_remove()
