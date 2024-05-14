"""Matter entity base class."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any, cast

from chip.clusters.Objects import ClusterAttributeDescriptor, NullValue
from matter_server.common.helpers.util import create_attribute_path
from matter_server.common.models import EventType, ServerInfoMessage

from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN, ID_TYPE_DEVICE_ID
from .helpers import get_device_id

if TYPE_CHECKING:
    from matter_server.client import MatterClient
    from matter_server.client.models.node import MatterEndpoint

    from .discovery import MatterEntityInfo

LOGGER = logging.getLogger(__name__)

# For some manually polled values (e.g. custom clusters) we perform
# an additional poll as soon as a secondary value changes.
# For example update the energy consumption meter when a relay is toggled
# of an energy metering powerplug. The below constant defined the delay after
# which we poll the primary value (debounced).
EXTRA_POLL_DELAY = 3.0


@dataclass(frozen=True)
class MatterEntityDescription(EntityDescription):
    """Describe the Matter entity."""

    # convert the value from the primary attribute to the value used by HA
    measurement_to_ha: Callable[[Any], Any] | None = None


class MatterEntity(Entity):
    """Entity class for Matter devices."""

    _attr_has_entity_name = True

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
        self._attr_should_poll = entity_info.should_poll
        self._extra_poll_timer_unsub: CALLBACK_TYPE | None = None

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

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        if self._extra_poll_timer_unsub:
            self._extra_poll_timer_unsub()
        for unsub in self._unsubscribes:
            with suppress(ValueError):
                # suppress ValueError to prevent race conditions
                unsub()

    async def async_update(self) -> None:
        """Call when the entity needs to be updated."""
        if not self._endpoint.node.available:
            # skip poll when the node is not (yet) available
            return
        # manually poll/refresh the primary value
        await self.matter_client.refresh_attribute(
            self._endpoint.node.node_id,
            self.get_matter_attribute_path(self._entity_info.primary_attribute),
        )
        self._update_from_device()

    @callback
    def _on_matter_event(self, event: EventType, data: Any = None) -> None:
        """Call on update from the device."""
        self._attr_available = self._endpoint.node.available
        if self._attr_should_poll:
            # secondary attribute updated of a polled primary value
            # enforce poll of the primary value a few seconds later
            if self._extra_poll_timer_unsub:
                self._extra_poll_timer_unsub()
            self._extra_poll_timer_unsub = async_call_later(
                self.hass, EXTRA_POLL_DELAY, self._do_extra_poll
            )
            return
        self._update_from_device()
        self.async_write_ha_state()

    @callback
    @abstractmethod
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

    @callback
    def _do_extra_poll(self, called_at: datetime) -> None:
        """Perform (extra) poll of primary value."""
        # scheduling the regulat update is enough to perform a poll/refresh
        self.async_schedule_update_ha_state(True)
