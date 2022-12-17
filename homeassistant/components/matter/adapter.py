"""Matter to Home Assistant adapter."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from chip.clusters import Objects as all_clusters
from matter_server.common.models.node_device import AbstractMatterNodeDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .device_platform import DEVICE_PLATFORM

if TYPE_CHECKING:
    from matter_server.client import MatterClient
    from matter_server.common.models.node import MatterNode


class MatterAdapter:
    """Connect Matter into Home Assistant."""

    def __init__(
        self,
        hass: HomeAssistant,
        matter_client: MatterClient,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the adapter."""
        self.matter_client = matter_client
        self.hass = hass
        self.config_entry = config_entry
        self.logger = logging.getLogger(__name__)
        self.platform_handlers: dict[Platform, AddEntitiesCallback] = {}
        self._platforms_set_up = asyncio.Event()

    def register_platform_handler(
        self, platform: Platform, add_entities: AddEntitiesCallback
    ) -> None:
        """Register a platform handler."""
        self.platform_handlers[platform] = add_entities
        if len(self.platform_handlers) == len(DEVICE_PLATFORM):
            self._platforms_set_up.set()

    async def setup_nodes(self) -> None:
        """Set up all existing nodes."""
        await self._platforms_set_up.wait()
        for node in await self.matter_client.get_nodes():
            await self._setup_node(node)

    async def _setup_node(self, node: MatterNode) -> None:
        """Set up an node."""
        self.logger.debug("Setting up entities for node %s", node.node_id)

        bridge_unique_id: str | None = None

        if node.aggregator_device_type_instance is not None:
            node_info = node.root_device_type_instance.get_cluster(all_clusters.Basic)
            self._create_device_registry(
                node_info, node_info.nodeLabel or "Hub device", None
            )
            bridge_unique_id = node_info.uniqueID

        for node_device in node.node_devices:
            self._setup_node_device(node_device, bridge_unique_id)

    def _create_device_registry(
        self,
        info: all_clusters.Basic | all_clusters.BridgedDeviceBasic,
        name: str,
        bridge_unique_id: str | None,
    ) -> None:
        """Create a device registry entry."""
        dr.async_get(self.hass).async_get_or_create(
            name=name,
            config_entry_id=self.config_entry.entry_id,
            identifiers={(DOMAIN, info.uniqueID)},
            hw_version=info.hardwareVersionString,
            sw_version=info.softwareVersionString,
            manufacturer=info.vendorName,
            model=info.productName,
            via_device=(DOMAIN, bridge_unique_id) if bridge_unique_id else None,
        )

    def _setup_node_device(
        self, node_device: AbstractMatterNodeDevice, bridge_unique_id: str | None
    ) -> None:
        """Set up a node device."""
        node = node_device.node()
        basic_info = node_device.device_info()
        device_type_instances = node_device.device_type_instances()

        name = basic_info.nodeLabel
        if not name and device_type_instances:
            name = f"{device_type_instances[0].device_type.__doc__[:-1]} {node.node_id}"

        self._create_device_registry(basic_info, name, bridge_unique_id)

        for instance in device_type_instances:
            created = False

            for platform, devices in DEVICE_PLATFORM.items():
                entity_descriptions = devices.get(instance.device_type)

                if entity_descriptions is None:
                    continue

                if not isinstance(entity_descriptions, list):
                    entity_descriptions = [entity_descriptions]

                entities = []
                for entity_description in entity_descriptions:
                    self.logger.debug(
                        "Creating %s entity for %s (%s)",
                        platform,
                        instance.device_type.__name__,
                        hex(instance.device_type.device_type),
                    )
                    entities.append(
                        entity_description.entity_cls(
                            self.matter_client,
                            node_device,
                            instance,
                            entity_description,
                        )
                    )

                self.platform_handlers[platform](entities)
                created = True

            if not created:
                self.logger.warning(
                    "Found unsupported device %s (%s)",
                    type(instance).__name__,
                    hex(instance.device_type.device_type),
                )
