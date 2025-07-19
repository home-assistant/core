"""Support for VELUX KLF 200 devices."""

from pyvlx import Node

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class VeluxEntity(Entity):
    """Abstraction for all Velux entities."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, node: Node, config_entry_id: str) -> None:
        """Initialize the Velux device."""
        self.node = node
        self._attr_unique_id = (
            node.serial_number
            if node.serial_number
            else f"{config_entry_id}_{node.node_id}"
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            {
                "identifiers": {
                    (
                        DOMAIN,
                        self.node.serial_number
                        if self.node.serial_number
                        else str(self.node.node_id),
                    )
                },
                "name": self.node.name if self.node.name else f"#{self.node.node_id}",
                "serial_number": self.node.serial_number,
            }
        )

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
