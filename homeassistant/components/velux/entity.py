"""Support for VELUX KLF 200 devices."""

from pyvlx import Node

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity


class VeluxEntity(Entity):
    """Abstraction for al Velux entities."""

    _attr_should_poll = False

    def __init__(self, node: Node, config_entry_id: str) -> None:
        """Initialize the Velux device."""
        self.node = node
        self._attr_unique_id = (
            node.serial_number
            if node.serial_number
            else f"{config_entry_id}_{node.node_id}"
        )
        self._attr_name = node.name if node.name else f"#{node.node_id}"

    @callback
    def async_register_callbacks(self):
        """Register callbacks to update hass after device was changed."""

        async def after_update_callback(device):
            """Call after device was updated."""
            self.async_write_ha_state()

        self.node.register_device_updated_cb(after_update_callback)

    async def async_added_to_hass(self) -> None:
        """Store register state change callback."""
        self.async_register_callbacks()
