"""LoRaWAN connection handling."""

from collections.abc import Callable
from dataclasses import dataclass, field, replace

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
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.service_info.lorawan import LoRaWANDiscoveryInfo
from homeassistant.util.hass_dict import HassKey

from .const import SIGNAL_DEVICES_CHANGED
from .device_state import DeviceState, ObservedConnection

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
    observed_connections: dict[str, ObservedConnection] = field(default_factory=dict)
    """Connection metadata and observations keyed by config entry ID."""
    connection_change_listeners: list[Callable[[ConnectionChange], None]] = field(
        default_factory=list
    )
    pending_connection_registrations: set[str] = field(default_factory=set)


DATA_REGISTRY: HassKey[ConnectionRegistry] = HassKey("lorawan")


async def async_register_connection(
    hass: HomeAssistant,
    entry: ConfigEntry,
    *,
    connection: Connection,
    configuration_url: str | None = None,
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
    devices: dict[str, DeviceState] = {}
    previous_connection = registry.observed_connections.get(entry_id)
    previous_devices = previous_connection.devices if previous_connection else {}
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
        if disconnected:
            return
        if event.type in (EventType.ADDED, EventType.UPDATED):
            if (state := devices.get(event.dev_eui)) is not None:
                state.descriptor = event.descriptor
            elif (previous := previous_devices.get(event.dev_eui)) is not None:
                devices[event.dev_eui] = replace(previous, descriptor=event.descriptor)
            else:
                devices[event.dev_eui] = DeviceState(event.descriptor)
        elif event.type == EventType.REMOVED:
            devices.pop(event.dev_eui, None)
        elif (state := devices.get(event.dev_eui)) is None or not state.receive(event):
            return
        if active:
            async_dispatcher_send(hass, SIGNAL_DEVICES_CHANGED)
        if event.type != EventType.ADDED:
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
            async_dispatcher_send(hass, SIGNAL_DEVICES_CHANGED)
            change: ConnectionChange = (entry_id, None)
            notify(registry.connection_change_listeners, change)
        for unsubscribe in unsubscribes:
            unsubscribe()
        unsubscribes.clear()

    try:
        unsubscribes.append(connection.on_disconnect(unregister))
        unsubscribes.append(
            await connection.async_subscribe(
                brands=None,
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
    registry.observed_connections[entry_id] = ObservedConnection(
        configuration_url, devices
    )
    previous_devices = {}
    active = True
    async_dispatcher_send(hass, SIGNAL_DEVICES_CHANGED)
    change: ConnectionChange = (entry_id, connection)
    notify(registry.connection_change_listeners, change)
    for domain in sorted(pending_discoveries):
        discover(domain)
    return unregister
