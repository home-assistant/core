"""Base Entities for Homee integration."""

from pyHomee.const import AttributeType, NodeProfile
from pyHomee.model import HomeeNode

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from . import HomeeConfigEntry
from .const import DOMAIN
from .helpers import get_name_for_enum


class HomeeNodeEntity(Entity):
    """Representation of an Entity that uses more than one HomeeAttribute."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, node: HomeeNode, entry: HomeeConfigEntry) -> None:
        """Initialize the wrapper using a HomeeNode and target entity."""
        self._node = node
        self._attr_unique_id = f"{entry.runtime_data.settings.uid}-{node.id}"
        self._entry = entry

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._node.id)},
            name=self._node.name,
            model=get_name_for_enum(NodeProfile, self._node.profile),
            sw_version=self._get_software_version(),
            via_device=(DOMAIN, self._entry.runtime_data.settings.uid),
        )

    async def async_added_to_hass(self) -> None:
        """Add the homee binary sensor device to home assistant."""
        self.async_on_remove(self._node.add_on_changed_listener(self._on_node_updated))

    @property
    def available(self) -> bool:
        """Return the availability of the underlying node."""
        return self._node.state <= 1

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

    def has_attribute(self, attribute_type) -> bool:
        """Check if an attribute of the given type exists."""
        return attribute_type in self._node.attribute_map

    def is_reversed(self, attribute_type) -> bool:
        """Check if movement direction is reversed."""
        attribute = self._node.get_attribute_by_type(attribute_type)
        if hasattr(attribute.options, "reverse_control_ui"):
            if attribute.options.reverse_control_ui:
                return True

        return False

    async def async_set_value(self, attribute_type: int, value: float) -> None:
        """Set an attribute value on the homee node."""
        await self.async_set_value_by_id(
            self._node.get_attribute_by_type(attribute_type).id, value
        )

    async def async_set_value_by_id(self, attribute_id: int, value: float) -> None:
        """Set an attribute value on the homee node."""
        homee = self._entry.runtime_data
        await homee.set_value(self._node.id, attribute_id, value)

    def _on_node_updated(self, node: HomeeNode) -> None:
        self.schedule_update_ha_state()


class AttributeNotFoundException(Exception):
    """Raised if a requested attribute does not exist on a homee node."""

    def __init__(self, attributeType) -> None:
        """Initialize the exception."""
        self.attributeType = attributeType
