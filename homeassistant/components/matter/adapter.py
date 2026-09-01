"""Matter to Home Assistant adapter."""

from typing import TYPE_CHECKING, cast

from chip.clusters import Objects as clusters
from matter_server.client.models.device_types import BridgedNode
from matter_server.common.models import EventType, ServerInfoMessage

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

from .const import DOMAIN, ID_TYPE_DEVICE_ID, ID_TYPE_SERIAL, LOGGER
from .discovery import async_discover_entities
from .helpers import MatterConfigEntry, get_device_endpoint, get_device_id

if TYPE_CHECKING:
    from matter_server.client import MatterClient
    from matter_server.client.models.node import MatterEndpoint, MatterNode


def get_clean_name(name: str | None) -> str | None:
    """Strip spaces and null char from the name."""
    if name is None:
        return name
    name = name.replace("\x00", "")
    return name.strip() or None


class MatterAdapter:
    """Connect Matter into Home Assistant."""

    def __init__(
        self,
        hass: HomeAssistant,
        matter_client: MatterClient,
        config_entry: MatterConfigEntry,
    ) -> None:
        """Initialize the adapter."""
        self.matter_client = matter_client
        self.hass = hass
        self.config_entry = config_entry
        self.platform_handlers: dict[Platform, AddEntitiesCallback] = {}
        self.discovered_entities: set[str] = set()

    def register_platform_handler(
        self, platform: Platform, add_entities: AddEntitiesCallback
    ) -> None:
        """Register a platform handler."""
        self.platform_handlers[platform] = add_entities

    async def setup_nodes(self) -> None:
        """Set up all existing nodes and subscribe to new nodes."""
        for node in self.matter_client.get_nodes():
            self._setup_node(node)

        def node_added_callback(event: EventType, node: MatterNode) -> None:
            """Handle node added event."""
            self._setup_node(node)

        def node_updated_callback(event: EventType, node: MatterNode) -> None:
            """Handle node updated event."""
            if not node.available:
                return
            # We always run the discovery logic again,
            # because the firmware version could have been changed or features added.
            self._setup_node(node)

        def endpoint_added_callback(event: EventType, data: dict[str, int]) -> None:
            """Handle endpoint added event."""
            node = self.matter_client.get_node(data["node_id"])
            endpoint = node.endpoints[data["endpoint_id"]]
            # Ensure the bridge device (endpoint 0) is registered before a
            # bridged child endpoint resolves it as its via_device.
            device_endpoint = get_device_endpoint(endpoint)
            if (
                device_endpoint.is_bridged_device
                and node.endpoints[0] != device_endpoint
            ):
                self._setup_endpoint(node.endpoints[0])
            self._setup_endpoint(endpoint)

        def endpoint_removed_callback(event: EventType, data: dict[str, int]) -> None:
            """Handle endpoint removed event."""
            server_info = cast(ServerInfoMessage, self.matter_client.server_info)
            try:
                node = self.matter_client.get_node(data["node_id"])
            except KeyError:
                return  # race condition
            device_registry = dr.async_get(self.hass)
            endpoint = node.endpoints.get(data["endpoint_id"])
            if not endpoint:
                return  # race condition
            if get_device_endpoint(endpoint) != endpoint:
                # A composed device is represented by a single HA device, which is
                # only removed once its compose parent endpoint is removed.
                return
            node_device_id = get_device_id(server_info, endpoint)
            identifier = (DOMAIN, f"{ID_TYPE_DEVICE_ID}_{node_device_id}")
            if device := device_registry.async_get_device_by_identifier(
                identifier, self.config_entry.entry_id
            ):
                device_registry.async_remove_device(device.id)

        def node_removed_callback(event: EventType, node_id: int) -> None:
            """Handle node removed event."""
            try:
                node = self.matter_client.get_node(node_id)
            except KeyError:
                return  # race condition
            for endpoint_id in node.endpoints:
                endpoint_removed_callback(
                    EventType.ENDPOINT_REMOVED,
                    {"node_id": node_id, "endpoint_id": endpoint_id},
                )

        self.config_entry.async_on_unload(
            self.matter_client.subscribe_events(
                callback=endpoint_added_callback, event_filter=EventType.ENDPOINT_ADDED
            )
        )
        self.config_entry.async_on_unload(
            self.matter_client.subscribe_events(
                callback=endpoint_removed_callback,
                event_filter=EventType.ENDPOINT_REMOVED,
            )
        )
        self.config_entry.async_on_unload(
            self.matter_client.subscribe_events(
                callback=node_removed_callback, event_filter=EventType.NODE_REMOVED
            )
        )
        self.config_entry.async_on_unload(
            self.matter_client.subscribe_events(
                callback=node_added_callback, event_filter=EventType.NODE_ADDED
            )
        )
        self.config_entry.async_on_unload(
            self.matter_client.subscribe_events(
                callback=node_updated_callback, event_filter=EventType.NODE_UPDATED
            )
        )

    def _setup_node(self, node: MatterNode) -> None:
        """Set up an node."""
        LOGGER.debug("Setting up entities for node %s", node.node_id)
        try:
            # Process endpoints in order so the bridge device (endpoint 0) is
            # registered before any bridged child endpoint resolves it as its
            # via_device.
            for endpoint_id in sorted(node.endpoints):
                # Node endpoints are translated into HA devices
                self._setup_endpoint(node.endpoints[endpoint_id])
        except Exception as err:  # noqa: BLE001
            # We don't want to crash the whole setup when a single node fails to setup
            # for whatever reason, so we catch all exceptions here.
            LOGGER.exception(
                "Error setting up node %s: %s",
                node.node_id,
                err,
            )

    def _create_device_registry(
        self,
        endpoint: MatterEndpoint,
    ) -> None:
        """Create a device registry entry for a MatterNode."""
        server_info = cast(ServerInfoMessage, self.matter_client.server_info)

        # All endpoints of a composed device share a single device registry entry,
        # so derive that entry from the compose parent for every one of them.
        endpoint = get_device_endpoint(endpoint)

        basic_info = endpoint.device_info
        # use (first) DeviceType of the endpoint as fallback product name
        device_type = next(
            (
                x
                for x in endpoint.device_types
                if x.device_type != BridgedNode.device_type
            ),
            None,
        )
        name = (
            get_clean_name(basic_info.nodeLabel)
            or get_clean_name(basic_info.productLabel)
            or get_clean_name(basic_info.productName)
            or (device_type.__name__ if device_type else None)
        )

        device_registry = dr.async_get(self.hass)

        # handle bridged devices
        via_device_id: str | UndefinedType = UNDEFINED
        if endpoint.is_bridged_device and endpoint.node.endpoints[0] != endpoint:
            bridge_device_id = get_device_id(
                server_info,
                endpoint.node.endpoints[0],
            )
            via_device_id = dr.async_get_device_id_by_identifier(
                self.hass,
                (DOMAIN, f"{ID_TYPE_DEVICE_ID}_{bridge_device_id}"),
                config_entry_id=self.config_entry.entry_id,
            )

        node_device_id = get_device_id(
            server_info,
            endpoint,
        )
        node_device_identifier = (DOMAIN, f"{ID_TYPE_DEVICE_ID}_{node_device_id}")
        identifiers = {node_device_identifier}
        serial_number: str | None = None
        # if available, we also add the serial number as identifier
        if (
            (basic_info_serial_number := basic_info.serialNumber)
            and "test" not in basic_info_serial_number.lower()
            # some bridges report their own serial number for the devices they bridge,
            # which would make the identifier resolve to the bridge's device
            and not (
                isinstance(basic_info, clusters.BridgedDeviceBasicInformation)
                and basic_info_serial_number == endpoint.node.device_info.serialNumber
            )
        ):
            # prefix identifier with 'serial_' to be able to filter it
            identifiers.add((DOMAIN, f"{ID_TYPE_SERIAL}_{basic_info_serial_number}"))
            serial_number = basic_info_serial_number

        # the bridge's device entry keeps every identifier that was ever merged onto
        # it, so a bridged device can still resolve to it through one left behind
        if (
            via_device_id is not UNDEFINED
            and (via_device := device_registry.async_get(via_device_id))
            and (stale_identifiers := via_device.identifiers & identifiers)
        ):
            device_registry.async_update_device(
                via_device.id,
                new_identifiers=via_device.identifiers - stale_identifiers,
            )

        # Model name is the human readable name of the model/product name
        model_name = (
            # productLabel is optional but preferred (e.g. Hue Bloom)
            get_clean_name(basic_info.productLabel)
            # alternative is the productName (e.g. LCT001)
            or get_clean_name(basic_info.productName)
            # if no product name, use the device type name
            or (device_type.__name__ if device_type else None)
        )
        # Model ID is the non-human readable product ID
        # we prefer the matter product ID so we can look it up in Matter DCL
        if isinstance(basic_info, clusters.BridgedDeviceBasicInformation):
            # On bridged devices, the productID is not available
            model_id = None
        else:
            model_id = str(product_id) if (product_id := basic_info.productID) else None

        device_registry.async_get_or_create(
            name=name,
            config_entry_id=self.config_entry.entry_id,
            identifiers=identifiers,
            hw_version=basic_info.hardwareVersionString,
            sw_version=basic_info.softwareVersionString,
            manufacturer=basic_info.vendorName or endpoint.node.device_info.vendorName,
            model=model_name,
            model_id=model_id,
            serial_number=serial_number,
            via_device_id=via_device_id,
        )

    def _setup_endpoint(self, endpoint: MatterEndpoint) -> None:
        """Set up a MatterEndpoint as HA Device."""
        # pre-create device registry entry
        self._create_device_registry(endpoint)
        # run platform discovery from device type instances
        for entity_info in async_discover_entities(endpoint):
            discovery_key = (
                f"{entity_info.platform}_{endpoint.node.node_id}_{endpoint.endpoint_id}_"
                f"{entity_info.primary_attribute.cluster_id}_"
                f"{entity_info.primary_attribute.attribute_id}_"
                f"{entity_info.entity_description.key}"
            )
            if discovery_key in self.discovered_entities:
                continue
            LOGGER.debug(
                "Creating %s entity for %s",
                entity_info.platform,
                entity_info.primary_attribute,
            )
            self.discovered_entities.add(discovery_key)
            new_entity = entity_info.entity_class(
                self.matter_client, endpoint, entity_info
            )
            self.platform_handlers[entity_info.platform]([new_entity])
