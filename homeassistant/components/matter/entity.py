"""Matter entity base class."""
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from matter_server.client.exceptions import FailedCommand
from matter_server.client.model.device_type_instance import MatterDeviceTypeInstance
from matter_server.client.model.node_device import AbstractMatterNodeDevice

from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription

from .const import DOMAIN


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
    _unsubscribe: Callable[..., Coroutine[Any, Any, None]] | None = None

    def __init__(
        self,
        node_device: AbstractMatterNodeDevice,
        device_type_instance: MatterDeviceTypeInstance,
        entity_description: MatterEntityDescriptionBaseClass,
    ) -> None:
        """Initialize the entity."""
        self._node_device = node_device
        self._device_type_instance = device_type_instance
        self.entity_description = entity_description
        node = device_type_instance.node
        self._attr_unique_id = f"{node.matter.client.server_info.compressedFabricId}-{node.unique_id}-{device_type_instance.endpoint_id}-{device_type_instance.device_type.device_type}"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device info for device registry."""
        return {"identifiers": {(DOMAIN, self._node_device.device_info().uniqueID)}}

    async def init_matter_device(self) -> None:
        """Initialize and subscribe device attributes."""
        try:
            # Subscribe to updates.
            self._unsubscribe = await self._device_type_instance.subscribe_updates(
                self.entity_description.subscribe_attributes,
                self._subscription_update,
            )

            # Fetch latest info from the device.
            await self._device_type_instance.update_attributes(
                self.entity_description.subscribe_attributes
            )
        except FailedCommand as err:
            self._device_type_instance.node.matter.adapter.logger.warning(
                "Error interacting with node %d (%s): %s. Marking device as unavailable. Recovery is not implemented yet. Reload config entry when device is available again.",
                self._device_type_instance.node.node_id,
                self.entity_id,
                str(err.error_code),
            )
            self._attr_available = False

        self._update_from_device()

    async def async_added_to_hass(self) -> None:
        """Handle being added to Home Assistant."""
        await super().async_added_to_hass()

        if not self.entity_description.subscribe_attributes:
            self._update_from_device()
            return

        async with self._device_type_instance.node.matter.adapter.get_node_lock(
            self._device_type_instance.node.node_id
        ):
            await self.init_matter_device()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        if self._unsubscribe is not None:
            await self._unsubscribe()

    @callback
    def _subscription_update(self) -> None:
        """Call when subscription is updated."""
        self._update_from_device()
        self.async_write_ha_state()

    @callback
    @abstractmethod
    def _update_from_device(self) -> None:
        """Update data from Matter device."""
