"""Base entity for Flic Button integration."""

from typing import override

from pyflic_ble import FlicState

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from . import FlicButtonData
from .const import DOMAIN


class FlicButtonEntity(Entity):
    """Base entity for Flic Button integration."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, data: FlicButtonData) -> None:
        """Initialize the Flic button entity."""
        client = data.client
        # The device is created and kept up to date in async_setup_entry
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, client.address)})
        self._client = client

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return self._client.state.connected

    @override
    async def async_added_to_hass(self) -> None:
        """Register state callback when entity is added."""
        await super().async_added_to_hass()

        self.async_on_remove(
            self._client.register_state_callback(self._handle_state_update)
        )

    @callback
    def _handle_state_update(self, state: FlicState) -> None:
        """Handle state updates from the client."""
        self.async_write_ha_state()
