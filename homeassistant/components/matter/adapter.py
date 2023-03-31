"""Matter to Home Assistant adapter."""
from __future__ import annotations

from typing import TYPE_CHECKING, cast

from matter_server.common.models import EventType, ServerInfoMessage

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, ID_TYPE_DEVICE_ID, ID_TYPE_SERIAL, LOGGER
from .discovery import async_discover_entities
from .helpers import get_device_id

if TYPE_CHECKING:
    from matter_server.client import MatterClient
    from matter_server.client.models.node import MatterEndpoint, MatterNode


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

        def node_added_callback(event: EventType, node: MatterNode) -> None:
            """Handle node added event."""
            self._setup_node(node)

        self.config_entry.async_on_unload(
            self.matter_client.subscribe(node_added_callback, EventType.NODE_ADDED)
        )

    def _setup_node(self, node: MatterNode) -> None:
        """Set up an node."""
        LOGGER.debug("Setting up entities for node %s", node.node_id)

        for endpoint in node.endpoints.values():
            # Node endpoints are translated into HA devices
            self._setup_endpoint(endpoint)

    def _create_device_registry(
        self,
        endpoint: MatterEndpoint,
    ) -> None:
        """Create a device registry entry for a MatterNode."""
        server_info = cast(ServerInfoMessage, self.matter_client.server_info)

        basic_info = endpoint.device_info
        name = basic_info.nodeLabel or basic_info.productLabel or basic_info.productName

        # handle bridged devices
        bridge_device_id = None
        if endpoint.is_bridged_device:
            bridge_device_id = get_device_id(
                server_info,
                endpoint.node.endpoints[0],
            )
            bridge_device_id = f"{ID_TYPE_DEVICE_ID}_{bridge_device_id}"

        node_device_id = get_device_id(
            server_info,
            endpoint,
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
            via_device=(DOMAIN, bridge_device_id) if bridge_device_id else None,
        )

    def _setup_endpoint(self, endpoint: MatterEndpoint) -> None:
        """Set up a MatterEndpoint as HA Device."""
        # pre-create device registry entry
        self._create_device_registry(endpoint)
        # run platform discovery from device type instances
        for entity_info in async_discover_entities(endpoint):
            LOGGER.debug(
                "Creating %s entity for %s",
                entity_info.platform,
                entity_info.primary_attribute,
            )
            new_entity = entity_info.entity_class(
                self.matter_client, endpoint, entity_info
            )
            self.platform_handlers[entity_info.platform]([new_entity])
