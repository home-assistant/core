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
    subscribe,
)

from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY, ConfigEntry
from homeassistant.core import HomeAssistant, callback as hass_callback
from homeassistant.helpers import discovery_flow
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
    connections: dict[str, RegisteredConnection] = field(default_factory=dict)
    changed: list[Callable[[ConnectionChange], None]] = field(default_factory=list)
    pending: set[str] = field(default_factory=set)


DATA_REGISTRY: HassKey[ConnectionRegistry] = HassKey("lorawan")


@hass_callback
def async_get_connections(hass: HomeAssistant) -> dict[str, Connection]:
    """Return connected backends keyed by their provider config entry ID."""
    return {
        entry_id: registered.connection
        for entry_id, registered in hass.data[DATA_REGISTRY].connections.items()
    }


@hass_callback
def async_subscribe_connections(
    hass: HomeAssistant, callback: Callable[[str, Connection | None], None]
) -> Unsubscribe:
    """Replay active connections, then report registrations and withdrawals.

    A withdrawn connection is reported as None. The caller owns any device-event
    subscriptions it creates and removes this listener on unload.
    """
    registry = hass.data[DATA_REGISTRY]
    unsubscribe = subscribe(registry.changed, lambda change: callback(*change))
    try:
        for entry_id, registered in tuple(registry.connections.items()):
            if registry.connections.get(entry_id) is registered:
                callback(entry_id, registered.connection)
    except BaseException:
        unsubscribe()
        raise
    return unsubscribe


async def async_register_connection(
    hass: HomeAssistant, entry: ConfigEntry, *, connection: Connection
) -> Unsubscribe:
    """Register a connected backend from lorawan-connection and return cleanup.

    Providers own transport setup, recovery, and shutdown. Register this cleanup
    with entry.async_on_unload(). Registration waits for discovery's inventory
    replay but stores no device inventory or status.
    """
    registry = hass.data[DATA_REGISTRY]
    entry_id = entry.entry_id
    if entry_id in registry.connections or entry_id in registry.pending:
        raise ValueError("A connection is already registered for this entry")
    registry.pending.add(entry_id)
    active = False
    disconnected = False
    pending_discoveries: set[str] = set()
    unsubscribes: list[Unsubscribe] = []

    @hass_callback
    def discover(domain: str) -> None:
        discovery_flow.async_create_flow(
            hass, domain, context={"source": SOURCE_INTEGRATION_DISCOVERY}, data={}
        )

    @hass_callback
    def handle_event(event: DeviceEvent) -> None:
        if (
            disconnected
            or event.network_id != entry_id
            or event.type == EventType.REMOVED
            or (descriptor := event.descriptor) is None
        ):
            return
        for domain, brands in registry.integrations.items():
            if (descriptor.stack, descriptor.brand_id) in brands:
                if active:
                    discover(domain)
                else:
                    pending_discoveries.add(domain)

    @hass_callback
    def unregister() -> None:
        nonlocal active, disconnected
        disconnected = True
        if active:
            active = False
            registry.connections.pop(entry_id)
            change: ConnectionChange = (entry_id, None)
            notify(registry.changed, change)
        for unsubscribe in unsubscribes:
            unsubscribe()
        unsubscribes.clear()

    try:
        unsubscribes.append(connection.on_disconnect(unregister))
        unsubscribes.append(
            await connection.async_subscribe(
                brands=frozenset(
                    pair for brands in registry.integrations.values() for pair in brands
                ),
                callback=handle_event,
            )
        )
    except BaseException:
        unregister()
        raise
    finally:
        registry.pending.discard(entry_id)

    if disconnected:
        unregister()
        raise ConnectionUnavailable("Connection lost during registration")
    registry.connections[entry_id] = RegisteredConnection(connection, unregister)
    active = True
    change: ConnectionChange = (entry_id, connection)
    notify(registry.changed, change)
    if active:
        for domain in sorted(pending_discoveries):
            discover(domain)
    return unregister
