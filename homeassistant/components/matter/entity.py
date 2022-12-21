"""Matter entity base class."""
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from matter_server.common.models.device_type_instance import MatterDeviceTypeInstance
from matter_server.common.models.events import EventType
from matter_server.common.models.node_device import AbstractMatterNodeDevice

from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription

from .const import DOMAIN

if TYPE_CHECKING:
    from matter_server.client import MatterClient
    from matter_server.common.models.node import MatterAttribute

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
        node = device_type_instance.node
        self._unsubscribes: list[Callable] = []
        # for fast lookups we create a mapping to the attribute paths
        self._attributes_map: dict[type, str] = {}
        self._attr_unique_id = f"{matter_client.server_info.compressed_fabric_id}-{node.unique_id}-{device_type_instance.endpoint}-{device_type_instance.device_type.device_type}"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device info for device registry."""
        return {"identifiers": {(DOMAIN, self._node_device.device_info().uniqueID)}}

    async def async_added_to_hass(self) -> None:
        """Handle being added to Home Assistant."""
        await super().async_added_to_hass()

        # Subscribe to attribute updates.
        for attr_cls in self.entity_description.subscribe_attributes:
            if matter_attr := self.get_matter_attribute(attr_cls):
                self._attributes_map[attr_cls] = matter_attr.path
                self._unsubscribes.append(
                    self.matter_client.subscribe(
                        self._on_matter_event,
                        EventType.ATTRIBUTE_UPDATED,
                        self._device_type_instance.node.node_id,
                        matter_attr.path,
                    )
                )
                continue
            # not sure if this can happen, but just in case log it.
            LOGGER.warning("Attribute not found on device: %s", attr_cls)

        # make sure to update the attributes once
        self._update_from_device()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        for unsub in self._unsubscribes:
            unsub()

    @callback
    def _on_matter_event(self, event: EventType, data: Any = None) -> None:
        """Call on update."""
        self._update_from_device()
        self.async_write_ha_state()

    @callback
    @abstractmethod
    def _update_from_device(self) -> None:
        """Update data from Matter device."""

    @callback
    def get_matter_attribute(self, attribute: type) -> MatterAttribute | None:
        """Lookup MatterAttribute instance on device instance by providing the attribute class."""
        return next(
            (
                x
                for x in self._device_type_instance.attributes
                if x.attribute_type == attribute
            ),
            None,
        )
