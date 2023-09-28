"""Support for Xiaomi Yeelight WiFi color bulb."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .device import YeelightDevice


class YeelightEntity(Entity):
    """Represents single Yeelight entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, device: YeelightDevice, entry: ConfigEntry) -> None:
        """Initialize the entity."""
        self._device = device
        self._unique_id = entry.unique_id or entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._unique_id)},
            name=self._device.name,
            manufacturer="Yeelight",
            model=self._device.model,
            sw_version=self._device.fw_version,
        )

    @property
    def unique_id(self) -> str:
        """Return the unique ID."""
        return self._unique_id

    @property
    def available(self) -> bool:
        """Return if bulb is available."""
        return self._device.available

    async def async_update(self) -> None:
        """Update the entity."""
        await self._device.async_update()
