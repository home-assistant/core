"""The WiLight integration."""

from typing import Any

from pywilight.wilight_device import PyWiLightDevice

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class WiLightDevice(Entity):
    """Representation of a WiLight device.

    Contains the common logic for WiLight entities.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, api_device: PyWiLightDevice, index: str, item_name: str) -> None:
        """Initialize the device."""
        # WiLight specific attributes for every component type
        self._device_id = api_device.device_id
        self._client = api_device.client
        self._index = index
        self._status: dict[str, Any] = {}

        self._attr_unique_id = f"{self._device_id}_{index}"
        self._attr_device_info = DeviceInfo(
            name=item_name,
            identifiers={(DOMAIN, self._attr_unique_id)},
            model=api_device.model,
            manufacturer="WiLight",
            sw_version=api_device.swversion,
            via_device=(DOMAIN, self._device_id),
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(self._client.is_connected)

    @callback
    def handle_event_callback(self, states: dict[str, Any]) -> None:
        """Propagate changes through ha."""
        self._status = states
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Synchronize state with api_device."""
        await self._client.status(self._index)

    async def async_added_to_hass(self) -> None:
        """Register update callback."""
        self._client.register_status_callback(self.handle_event_callback, self._index)
        await self._client.status(self._index)
