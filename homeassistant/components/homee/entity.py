"""Base Entities for Homee integration."""

from pyHomee.const import AttributeState, AttributeType, NodeProfile, NodeState
from pyHomee.model import HomeeAttribute, HomeeNode

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from . import HomeeConfigEntry
from .const import DOMAIN
from .helpers import get_name_for_enum


class HomeeEntity(Entity):
    """Represents a Homee entity consisting of a single HomeeAttribute."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, attribute: HomeeAttribute, entry: HomeeConfigEntry) -> None:
        """Initialize the wrapper using a HomeeAttribute and target entity."""
        self._attribute = attribute
        self._attr_unique_id = (
            f"{entry.runtime_data.settings.uid}-{attribute.node_id}-{attribute.id}"
        )
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, f"{entry.runtime_data.settings.uid}-{attribute.node_id}")
            }
        )

        self._host_connected = entry.runtime_data.connected

    async def async_added_to_hass(self) -> None:
        """Add the homee attribute entity to home assistant."""
        self.async_on_remove(
            self._attribute.add_on_changed_listener(self._on_node_updated)
        )
        self.async_on_remove(
            await self._entry.runtime_data.add_connection_listener(
                self._on_connection_changed
            )
        )

    @property
    def available(self) -> bool:
        """Return the availability of the underlying node."""
        return (self._attribute.state == AttributeState.NORMAL) and self._host_connected

    async def async_update(self) -> None:
        """Update entity from homee."""
        homee = self._entry.runtime_data
        await homee.update_attribute(self._attribute.node_id, self._attribute.id)

    def _on_node_updated(self, attribute: HomeeAttribute) -> None:
        self.schedule_update_ha_state()

    async def _on_connection_changed(self, connected: bool) -> None:
        self._host_connected = connected
        self.schedule_update_ha_state()


class HomeeNodeEntity(Entity):
    """Representation of an Entity that uses more than one HomeeAttribute."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, node: HomeeNode, entry: HomeeConfigEntry) -> None:
        """Initialize the wrapper using a HomeeNode and target entity."""
        self._node = node
        self._attr_unique_id = f"{entry.unique_id}-{node.id}"
        self._entry = entry

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(node.id))},
            name=node.name,
            model=get_name_for_enum(NodeProfile, node.profile),
            sw_version=self._get_software_version(),
            via_device=(DOMAIN, entry.runtime_data.settings.uid),
        )
        self._host_connected = entry.runtime_data.connected

    async def async_added_to_hass(self) -> None:
        """Add the homee binary sensor device to home assistant."""
        self.async_on_remove(self._node.add_on_changed_listener(self._on_node_updated))
        self.async_on_remove(
            await self._entry.runtime_data.add_connection_listener(
                self._on_connection_changed
            )
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        # Homee hub has id -1, but is identified only by the UID.
        if self._node.id == -1:
            return DeviceInfo(
                identifiers={(DOMAIN, self._entry.runtime_data.settings.uid)},
            )

        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.unique_id}-{self._node.id}")},
            name=self._node.name,
            model=get_name_for_enum(NodeProfile, self._node.profile),
            sw_version=self._get_software_version(),
            via_device=(DOMAIN, self._entry.runtime_data.settings.uid),
        )

    @property
    def available(self) -> bool:
        """Return the availability of the underlying node."""
        return self._node.state == NodeState.AVAILABLE and self._host_connected

    async def async_update(self) -> None:
        """Fetch new state data for this node."""
        # Base class requests the whole node, if only a single attribute is needed
        # the platform will overwrite this method.
        homee = self._entry.runtime_data
        await homee.update_node(self._node.id)

    def _get_software_version(self) -> str | None:
        """Return the software version of the node."""
        if self.has_attribute(AttributeType.FIRMWARE_REVISION):
            return self._node.get_attribute_by_type(
                AttributeType.FIRMWARE_REVISION
            ).get_value()
        if self.has_attribute(AttributeType.SOFTWARE_REVISION):
            return self._node.get_attribute_by_type(
                AttributeType.SOFTWARE_REVISION
            ).get_value()
        return None

    def has_attribute(self, attribute_type: AttributeType) -> bool:
        """Check if an attribute of the given type exists."""
        return attribute_type in self._node.attribute_map

    async def async_set_value(self, attribute: HomeeAttribute, value: float) -> None:
        """Set an attribute value on the homee node."""
        homee = self._entry.runtime_data
        await homee.set_value(attribute.node_id, attribute.id, value)

    def _on_node_updated(self, node: HomeeNode) -> None:
        self.schedule_update_ha_state()

    async def _on_connection_changed(self, connected: bool) -> None:
        self._host_connected = connected
        self.schedule_update_ha_state()
