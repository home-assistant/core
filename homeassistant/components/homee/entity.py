"""Base Entities for Homee integration."""

from pyHomee.const import AttributeType, NodeProfile
from pyHomee.model import HomeeAttribute, HomeeNode

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import Entity

from . import HomeeConfigEntry
from .const import DOMAIN
from .helpers import get_name_for_enum


class HomeeNodeEntity(Entity):
    """Representation of a Node in Homee."""

    _attr_has_entity_name = True

    def __init__(self, node: HomeeNode, entry: HomeeConfigEntry) -> None:
        """Initialize the wrapper using a HomeeNode and target entity."""
        self._node = node
        self._clear_node_listener = None
        self._attr_unique_id = node.id
        self._entry = entry

        self._homee_data = {
            "id": node.id,
            "name": node.name,
            "profile": node.profile,
            "attributes": [{"id": a.id, "type": a.type} for a in node.attributes],
        }
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, self._node.id)},
            name=self._node.name,
            manufacturer="unknown",
            model=get_name_for_enum(NodeProfile, self._homee_data["profile"]),
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

    @property
    def should_poll(self) -> bool:
        """Return if the entity should poll."""
        return False

    @property
    def raw_data(self):
        """Return the raw data of the node."""
        return self._node.raw_data

    async def async_update(self):
        """Fetch new state data for this node."""
        # Base class requests the whole node, if only a single attribute is needed
        # the platform will overwrite this method.
        homee = self._entry.runtime_data
        await homee.update_node(self._node.id)

    def attribute(self, attribute_type):
        """Try to get the current value of the attribute of the given type."""
        try:
            attribute = self._node.get_attribute_by_type(attribute_type)
        except KeyError:
            raise AttributeNotFoundException(attribute_type) from None

        # If the unit of the attribute is 'text', it is stored in .data
        if attribute.unit == "text":
            return self._node.get_attribute_by_type(attribute_type).data

        return self._node.get_attribute_by_type(attribute_type).current_value

    def _get_software_version(self) -> str:
        """Return the software version of the node."""
        if self.has_attribute(AttributeType.FIRMWARE_REVISION):
            sw_version = self.attribute(AttributeType.FIRMWARE_REVISION)
        elif self.has_attribute(AttributeType.SOFTWARE_REVISION):
            sw_version = self.attribute(AttributeType.SOFTWARE_REVISION)
        else:
            sw_version = None

        return sw_version

    def get_attribute(self, attribute_type):
        """Get the attribute object of the given type."""
        return self._node.get_attribute_by_type(attribute_type)

    def has_attribute(self, attribute_type):
        """Check if an attribute of the given type exists."""
        return attribute_type in self._node.attribute_map

    def is_reversed(self, attribute_type) -> bool:
        """Check if movement direction is reversed."""
        attribute = self._node.get_attribute_by_type(attribute_type)
        if hasattr(attribute.options, "reverse_control_ui"):
            if attribute.options.reverse_control_ui:
                return True

        return False

    async def async_set_value(self, attribute_type: int, value: float):
        """Set an attribute value on the homee node."""
        await self.async_set_value_by_id(self.get_attribute(attribute_type).id, value)

    async def async_set_value_by_id(self, attribute_id: int, value: float):
        """Set an attribute value on the homee node."""
        homee = self._entry.runtime_data
        await homee.set_value(self._node.id, attribute_id, value)

    def _on_node_updated(self, node: HomeeNode, attribute: HomeeAttribute):
        self.schedule_update_ha_state()


class AttributeNotFoundException(Exception):
    """Raised if a requested attribute does not exist on a homee node."""

    def __init__(self, attributeType) -> None:
        """Initialize the exception."""
        self.attributeType = attributeType
