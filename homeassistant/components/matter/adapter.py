"""Matter to Home Assistant adapter."""
from __future__ import annotations

from typing import TYPE_CHECKING, cast

from chip.clusters import Objects as all_clusters
from matter_server.common.models.events import EventType
from matter_server.common.models.node_device import (
    AbstractMatterNodeDevice,
    MatterBridgedNodeDevice,
)
from matter_server.common.models.server_information import ServerInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, ID_TYPE_DEVICE_ID, ID_TYPE_SERIAL, LOGGER
from .device_platform import DEVICE_PLATFORM
from .helpers import get_device_id

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
        self.platform_handlers: dict[Platform, AddEntitiesCallback] = {}

    def register_platform_handler(
        self, platform: Platform, add_entities: AddEntitiesCallback
    ) -> None:
        """Register a platform handler."""
        self.platform_handlers[platform] = add_entities

    async def setup_nodes(self) -> None:
        """Set up all existing nodes and subscribe to new nodes."""
        for node in await self.matter_client.get_nodes():
            self._setup_node(node)

        def node_added_callback(event: EventType, node: MatterNode | None) -> None:
            """Handle node added event."""
            if node is None:
                # We can clean this up when we've improved the typing in the library.
                # https://github.com/home-assistant-libs/python-matter-server/pull/153
                raise RuntimeError("Node added event without node")
            self._setup_node(node)

        self.config_entry.async_on_unload(
            self.matter_client.subscribe(node_added_callback, EventType.NODE_ADDED)
        )

    def _setup_node(self, node: MatterNode) -> None:
        """Set up an node."""
        LOGGER.debug("Setting up entities for node %s", node.node_id)

        bridge_unique_id: str | None = None

        if node.aggregator_device_type_instance is not None and (
            node.root_device_type_instance.get_cluster(all_clusters.BasicInformation)
        ):
            # create virtual (parent) device for bridge node device
            bridge_device = MatterBridgedNodeDevice(
                node.aggregator_device_type_instance
            )
            self._create_device_registry(bridge_device)
            server_info = cast(ServerInfo, self.matter_client.server_info)
            bridge_unique_id = get_device_id(server_info, bridge_device)

        for node_device in node.node_devices:
            self._setup_node_device(node_device, bridge_unique_id)

    def _create_device_registry(
        self,
        node_device: AbstractMatterNodeDevice,
        bridge_unique_id: str | None = None,
    ) -> None:
        """Create a device registry entry."""
        server_info = cast(ServerInfo, self.matter_client.server_info)

        basic_info = node_device.device_info()
        device_type_instances = node_device.device_type_instances()

        name = basic_info.nodeLabel
        if not name and isinstance(node_device, MatterBridgedNodeDevice):
            # fallback name for Bridge
            name = "Hub device"
        elif not name and device_type_instances:
            # use the productName if no node label is present
            name = basic_info.productName

        node_device_id = get_device_id(
            server_info,
            node_device,
        )
        identifiers = {(DOMAIN, f"{ID_TYPE_DEVICE_ID}_{node_device_id}")}
        # if available, we also add the serialnumber as identifier
        if basic_info.serialNumber and "test" not in basic_info.serialNumber.lower():
            # prefix identifier with 'serial_' to be able to filter it
            identifiers.add((DOMAIN, f"{ID_TYPE_SERIAL}_{basic_info.serialNumber}"))

        dr.async_get(self.hass).async_get_or_create(
            name=name,
            config_entry_id=self.config_entry.entry_id,
            identifiers=identifiers,
            hw_version=basic_info.hardwareVersionString,
            sw_version=basic_info.softwareVersionString,
            manufacturer=basic_info.vendorName,
            model=basic_info.productName,
            via_device=(DOMAIN, bridge_unique_id) if bridge_unique_id else None,
        )

    def _setup_node_device(
        self, node_device: AbstractMatterNodeDevice, bridge_unique_id: str | None
    ) -> None:
        """Set up a node device."""
        self._create_device_registry(node_device, bridge_unique_id)
        # run platform discovery from device type instances
        for instance in node_device.device_type_instances():
            created = False

            for platform, devices in DEVICE_PLATFORM.items():
                entity_descriptions = devices.get(instance.device_type)

                if entity_descriptions is None:
                    continue

                if not isinstance(entity_descriptions, list):
                    entity_descriptions = [entity_descriptions]

                entities = []
                for entity_description in entity_descriptions:
                    LOGGER.debug(
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
                LOGGER.warning(
                    "Found unsupported device %s (%s)",
                    type(instance).__name__,
                    hex(instance.device_type.device_type),
                )
