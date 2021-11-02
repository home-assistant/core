"""Generic HUE Entity Model."""
from __future__ import annotations

from aiohue.v2.controllers.base import BaseResourcesController
from aiohue.v2.controllers.events import EventType
from aiohue.v2.models.clip import CLIPResource
from aiohue.v2.models.connectivity import ConnectivityServiceStatus

from homeassistant.components.hue.bridge import HueBridge
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo, Entity

from ..const import DOMAIN as DOMAIN


class HueBaseEntity(Entity):
    """Generic Entity Class for a Hue resource."""

    _attr_should_poll = False

    def __init__(
        self,
        bridge: HueBridge,
        controller: BaseResourcesController,
        resource: CLIPResource,
    ) -> None:
        """Initialize a generic Hue resource entity."""
        self.bridge = bridge
        self.controller = controller
        self.resource = resource
        self.device = controller.get_device(resource.id)
        self.logger = bridge.logger.getChild(resource.type.value)

        # Entity class attributes
        self._attr_unique_id = resource.id
        # device is precreated in main handler
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device.id)},
        )

    @property
    def name(self) -> str:
        """Return name for the entity."""
        return getattr(self.resource, "name", self.device.metadata.name)

    async def async_added_to_hass(self) -> None:
        """Call when entity is added."""
        # Add value_changed callbacks.
        self.async_on_remove(
            self.controller.subscribe(
                self._handle_event,
                self.resource.id,
                (EventType.RESOURCE_UPDATED, EventType.RESOURCE_DELETED),
            )
        )

    @property
    def available(self) -> bool:
        """Return entity availability."""
        if self.bridge.allow_unreachable:
            return True
        if zigbee := self.controller.get_zigbee_connectivity(self.resource.id):
            return zigbee.status == ConnectivityServiceStatus.CONNECTED
        return True

    @callback
    def on_update(self) -> None:
        """Call on update event."""
        pass  # used in subclasses

    @callback
    def _handle_event(self, event_type: EventType, resource: CLIPResource) -> None:
        """Handle status event for this resource."""
        if event_type == EventType.RESOURCE_DELETED and resource.id == self.resource.id:
            self.logger.debug("Received delete for %s", self.entity_id)
            # non-device bound entities like groups and scenes need to be removed here
            # all others will be be removed by device setup in case of device removal
            self.hass.create_task(self.async_remove(force_remove=True))
        else:
            self.logger.debug("Received status update for %s", self.entity_id)
            self.on_update()
            self.async_write_ha_state()
