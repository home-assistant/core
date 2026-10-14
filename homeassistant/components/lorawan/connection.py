"""Register server connections and discover matching vendor integrations."""

from collections.abc import Callable
from dataclasses import dataclass, field

from lorawan_connection import (
    Connection,
    ConnectionUnavailable,
    DeviceEvent,
    EventType,
    Unsubscribe,
    notify,
)

from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY, ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import discovery_flow
from homeassistant.helpers.service_info.lorawan import LoRaWANDiscoveryInfo
from homeassistant.util.hass_dict import HassKey

type ConnectionChange = tuple[str, Connection | None]


@dataclass
class RegisteredConnection:
    """A provider and the cleanup for its discovery subscription."""

    connection: Connection
    unsubscribe: Unsubscribe


@dataclass
class ConnectionRegistry:
    """Keep connection registrations and manifest matchers."""

    integrations: dict[str, list[tuple[str, int | str]]]
    """Discovery matchers keyed by device integration domain."""
    connections: dict[str, RegisteredConnection] = field(default_factory=dict)
    """Registered connections keyed by provider config entry ID."""
    connection_change_listeners: list[Callable[[ConnectionChange], None]] = field(
        default_factory=list
    )
    pending_connection_registrations: set[str] = field(default_factory=set)


DATA_REGISTRY: HassKey[ConnectionRegistry] = HassKey("lorawan")


async def async_register_connection(
    hass: HomeAssistant, entry: ConfigEntry, *, connection: Connection
) -> Unsubscribe:
    """Register a connected backend from lorawan-connection and return cleanup."""
    registry = hass.data[DATA_REGISTRY]
    entry_id = entry.entry_id
    if (
        entry_id in registry.connections
        or entry_id in registry.pending_connection_registrations
    ):
        raise ValueError("A connection is already registered for this entry")
    discovery_brands = {}
    for domain, matchers in registry.integrations.items():
        brands = {
            brand_id for stack, brand_id in matchers if stack == connection.stack_type
        }
        if brands:
            discovery_brands[domain] = brands
    registry.pending_connection_registrations.add(entry_id)
    active = False
    disconnected = False
    pending_discoveries: set[str] = set()
    unsubscribes: list[Unsubscribe] = []

    @callback
    def discover(domain: str) -> None:
        discovery_flow.async_create_flow(
            hass,
            domain,
            context={"source": SOURCE_INTEGRATION_DISCOVERY},
            data=LoRaWANDiscoveryInfo(),
        )

    @callback
    def handle_event(event: DeviceEvent) -> None:
        if disconnected or event.type != EventType.ADDED:
            return
        brand_id = event.descriptor.brand_id
        for domain, brands in discovery_brands.items():
            if brand_id in brands:
                if active:
                    discover(domain)
                else:
                    pending_discoveries.add(domain)

    @callback
    def unregister() -> None:
        nonlocal active, disconnected
        disconnected = True
        if active:
            active = False
            registry.connections.pop(entry_id)
            change: ConnectionChange = (entry_id, None)
            notify(registry.connection_change_listeners, change)
        for unsubscribe in unsubscribes:
            unsubscribe()
        unsubscribes.clear()

    try:
        unsubscribes.append(connection.on_disconnect(unregister))
        unsubscribes.append(
            await connection.async_subscribe(
                brands=frozenset(
                    (connection.stack_type, brand_id)
                    for brands in discovery_brands.values()
                    for brand_id in brands
                ),
                listener=handle_event,
            )
        )
    except BaseException:
        unregister()
        raise
    finally:
        registry.pending_connection_registrations.discard(entry_id)

    if disconnected:
        unregister()
        raise ConnectionUnavailable("Connection lost during registration")
    registry.connections[entry_id] = RegisteredConnection(connection, unregister)
    active = True
    change: ConnectionChange = (entry_id, connection)
    notify(registry.connection_change_listeners, change)
    for domain in sorted(pending_discoveries):
        discover(domain)
    return unregister
