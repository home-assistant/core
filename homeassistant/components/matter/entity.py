"""Matter entity base class."""
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any, cast

from chip.clusters.Objects import ClusterAttributeDescriptor
from matter_server.client.models.device_type_instance import MatterDeviceTypeInstance
from matter_server.client.models.node_device import AbstractMatterNodeDevice
from matter_server.common.helpers.util import create_attribute_path
from matter_server.common.models import EventType, ServerInfoMessage

from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription

from .const import DOMAIN, ID_TYPE_DEVICE_ID
from .helpers import get_device_id, get_operational_instance_id

if TYPE_CHECKING:
    from matter_server.client import MatterClient

LOGGER = logging.getLogger(__name__)


@dataclass
class MatterEntityDescription:
    """Mixin to map a matter device to a Home Assistant entity."""

    entity_cls: type[MatterEntity]
    subscribe_attributes: tuple


@dataclass
class MatterEntityDescriptionBaseClass(EntityDescription, MatterEntityDescription):
    """For typing a base class that inherits from both entity descriptions."""


class MatterEntity(Entity):
    """Entity class for Matter devices."""

    entity_description: MatterEntityDescriptionBaseClass
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        matter_client: MatterClient,
        node_device: AbstractMatterNodeDevice,
        device_type_instance: MatterDeviceTypeInstance,
        entity_description: MatterEntityDescriptionBaseClass,
    ) -> None:
        """Initialize the entity."""
        self.matter_client = matter_client
        self._node_device = node_device
        self._device_type_instance = device_type_instance
        self.entity_description = entity_description
        self._unsubscribes: list[Callable] = []
        # for fast lookups we create a mapping to the attribute paths
        self._attributes_map: dict[type, str] = {}
        # The server info is set when the client connects to the server.
        server_info = cast(ServerInfoMessage, self.matter_client.server_info)
        # create unique_id based on "Operational Instance Name" and endpoint/device type
        self._attr_unique_id = (
            f"{get_operational_instance_id(server_info, self._node_device.node())}-"
            f"{device_type_instance.endpoint.endpoint_id}-"
            f"{device_type_instance.device_type.device_type}"
        )
        node_device_id = get_device_id(server_info, node_device)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{ID_TYPE_DEVICE_ID}_{node_device_id}")}
        )
        self._attr_available = self._node_device.node().available

    async def async_added_to_hass(self) -> None:
        """Handle being added to Home Assistant."""
        await super().async_added_to_hass()

        # Subscribe to attribute updates.
        for attr_cls in self.entity_description.subscribe_attributes:
            attr_path = self.get_matter_attribute_path(attr_cls)
            self._attributes_map[attr_cls] = attr_path
            self._unsubscribes.append(
                self.matter_client.subscribe(
                    callback=self._on_matter_event,
                    event_filter=EventType.ATTRIBUTE_UPDATED,
                    node_filter=self._device_type_instance.node.node_id,
                    attr_path_filter=attr_path,
                )
            )
        # subscribe to node (availability changes)
        self._unsubscribes.append(
            self.matter_client.subscribe(
                callback=self._on_matter_event,
                event_filter=EventType.NODE_UPDATED,
                node_filter=self._device_type_instance.node.node_id,
            )
        )

        # make sure to update the attributes once
        self._update_from_device()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        for unsub in self._unsubscribes:
            unsub()

    @callback
    def _on_matter_event(self, event: EventType, data: Any = None) -> None:
        """Call on update."""
        self._attr_available = self._device_type_instance.node.available
        self._update_from_device()
        self.async_write_ha_state()

    @callback
    @abstractmethod
    def _update_from_device(self) -> None:
        """Update data from Matter device."""

    @callback
    def get_matter_attribute_value(
        self, attribute: type[ClusterAttributeDescriptor]
    ) -> Any:
        """Get current value for given attribute."""
        return self._device_type_instance.get_attribute_value(None, attribute)

    @callback
    def get_matter_attribute_path(
        self, attribute: type[ClusterAttributeDescriptor]
    ) -> str:
        """Return AttributePath by providing the endpoint and Attribute class."""
        endpoint = self._device_type_instance.endpoint.endpoint_id
        return create_attribute_path(
            endpoint, attribute.cluster_id, attribute.attribute_id
        )
