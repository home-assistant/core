"""Generic Velux Entity."""

from pyvlx import Node

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class VeluxNodeEntity(Entity):
    """Abstraction for all pyvlx node entities."""

    _attr_should_poll = False

    def __init__(self, node: Node) -> None:
        """Initialize the Velux device."""
        self.node: Node = node

    async def after_update_callback(self, node: Node) -> None:
        """Call after device was updated."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Store register state change callback."""
        self.node.register_device_updated_cb(self.after_update_callback)

    @property
    def unique_id(self) -> str:
        """Return the unique ID of this entity."""
        # Some devices from other vendors does not provide a serial_number
        # Node_id is used instead, which is unique within velux component
        if self.node.serial_number is None:
            unique_id = str(self.node.node_id)
        else:
            unique_id = self.node.serial_number
        return unique_id

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        if not self.node.name:
            return "#" + str(self.node.node_id)
        return self.node.name

    @property
    def should_poll(self) -> bool:
        """No polling needed within Velux."""
        return False

    @property
    def device_info(self) -> DeviceInfo:
        """Return specific device attributes."""
        return {
            "identifiers": {(DOMAIN, str(self.node.node_id))},
            "name": self.name,
        }
