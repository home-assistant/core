"""Matter entity base class."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import cached_property
import logging
from typing import TYPE_CHECKING, Any, cast

from chip.clusters import Objects as clusters
from chip.clusters.Objects import ClusterAttributeDescriptor, NullValue
from matter_server.common.helpers.util import create_attribute_path
from matter_server.common.models import EventType, ServerInfoMessage

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.typing import UndefinedType

from .const import DOMAIN, ID_TYPE_DEVICE_ID
from .helpers import get_device_id

if TYPE_CHECKING:
    from matter_server.client import MatterClient
    from matter_server.client.models.node import MatterEndpoint

    from .discovery import MatterEntityInfo

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class MatterEntityDescription(EntityDescription):
    """Describe the Matter entity."""

    # convert the value from the primary attribute to the value used by HA
    measurement_to_ha: Callable[[Any], Any] | None = None
    ha_to_native_value: Callable[[Any], Any] | None = None


class MatterEntity(Entity):
    """Entity class for Matter devices."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _name_postfix: str | None = None

    def __init__(
        self,
        matter_client: MatterClient,
        endpoint: MatterEndpoint,
        entity_info: MatterEntityInfo,
    ) -> None:
        """Initialize the entity."""
        self.matter_client = matter_client
        self._endpoint = endpoint
        self._entity_info = entity_info
        self.entity_description = entity_info.entity_description
        self._unsubscribes: list[Callable] = []
        # for fast lookups we create a mapping to the attribute paths
        self._attributes_map: dict[type, str] = {}
        # The server info is set when the client connects to the server.
        server_info = cast(ServerInfoMessage, self.matter_client.server_info)
        # create unique_id based on "Operational Instance Name" and endpoint/device type
        node_device_id = get_device_id(server_info, endpoint)
        self._attr_unique_id = (
            f"{node_device_id}-"
            f"{endpoint.endpoint_id}-"
            f"{entity_info.entity_description.key}-"
            f"{entity_info.primary_attribute.cluster_id}-"
            f"{entity_info.primary_attribute.attribute_id}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{ID_TYPE_DEVICE_ID}_{node_device_id}")}
        )
        self._attr_available = self._endpoint.node.available
        # mark endpoint postfix if the device has the primary attribute on multiple endpoints
        if not self._endpoint.node.is_bridge_device and any(
            ep
            for ep in self._endpoint.node.endpoints.values()
            if ep != self._endpoint
            and ep.has_attribute(None, entity_info.primary_attribute)
        ):
            self._name_postfix = str(self._endpoint.endpoint_id)

        # prefer the label attribute for the entity name
        # Matter has a way for users and/or vendors to specify a name for an endpoint
        # which is always preferred over a standard HA (generated) name
        for attr in (
            clusters.FixedLabel.Attributes.LabelList,
            clusters.UserLabel.Attributes.LabelList,
        ):
            if not (labels := self.get_matter_attribute_value(attr)):
                continue
            for label in labels:
                if label.label not in ["Label", "Button"]:
                    continue
                # fixed or user label found: use it
                label_value: str = label.value
                # in the case the label is only the label id, use it as postfix only
                if label_value.isnumeric():
                    self._name_postfix = label_value
                else:
                    self._attr_name = label_value
                break

        # make sure to update the attributes once
        self._update_from_device()

    async def async_added_to_hass(self) -> None:
        """Handle being added to Home Assistant."""
        await super().async_added_to_hass()

        # Subscribe to attribute updates.
        sub_paths: list[str] = []
        for attr_cls in self._entity_info.attributes_to_watch:
            attr_path = self.get_matter_attribute_path(attr_cls)
            if attr_path in sub_paths:
                # prevent duplicate subscriptions
                continue
            self._attributes_map[attr_cls] = attr_path
            sub_paths.append(attr_path)
            self._unsubscribes.append(
                self.matter_client.subscribe_events(
                    callback=self._on_matter_event,
                    event_filter=EventType.ATTRIBUTE_UPDATED,
                    node_filter=self._endpoint.node.node_id,
                    attr_path_filter=attr_path,
                )
            )
        # subscribe to node (availability changes)
        self._unsubscribes.append(
            self.matter_client.subscribe_events(
                callback=self._on_matter_event,
                event_filter=EventType.NODE_UPDATED,
                node_filter=self._endpoint.node.node_id,
            )
        )

    @cached_property
    def name(self) -> str | UndefinedType | None:
        """Return the name of the entity."""
        if hasattr(self, "_attr_name"):
            # an explicit entity name was defined, we use that
            return self._attr_name
        name = super().name
        if name and self._name_postfix:
            name = f"{name} ({self._name_postfix})"
        return name

    @callback
    def _on_matter_event(self, event: EventType, data: Any = None) -> None:
        """Call on update from the device."""
        self._attr_available = self._endpoint.node.available
        self._update_from_device()
        self.async_write_ha_state()

    @callback
    def _update_from_device(self) -> None:
        """Update data from Matter device."""

    @callback
    def get_matter_attribute_value(
        self, attribute: type[ClusterAttributeDescriptor], null_as_none: bool = True
    ) -> Any:
        """Get current value for given attribute."""
        value = self._endpoint.get_attribute_value(None, attribute)
        if null_as_none and value == NullValue:
            return None
        return value

    @callback
    def get_matter_attribute_path(
        self, attribute: type[ClusterAttributeDescriptor]
    ) -> str:
        """Return AttributePath by providing the endpoint and Attribute class."""
        return create_attribute_path(
            self._endpoint.endpoint_id, attribute.cluster_id, attribute.attribute_id
        )
