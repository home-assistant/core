"""LoRaWAN connection handling."""

from collections.abc import Callable
from dataclasses import dataclass, field

from lorawan_connection import (
    Connection,
    ConnectionUnavailable,
    DeviceDescriptor,
    DeviceEvent,
    EventType,
    JoinEvent,
    StatusEvent,
    Unsubscribe,
    UplinkEvent,
    notify,
)

from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY, ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import discovery_flow
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.service_info.lorawan import LoRaWANDiscoveryInfo
from homeassistant.util.hass_dict import HassKey

from .const import SIGNAL_DEVICES_CHANGED

type ConnectionChange = tuple[str, Connection | None]


@dataclass
class DeviceState:
    """Keep the latest observations independently of a device integration."""

    descriptor: DeviceDescriptor
    uplink: UplinkEvent | None = None
    join: JoinEvent | None = None
    status: StatusEvent | None = None

    def receive(self, event: DeviceEvent) -> bool:
        """Update device metadata and the latest observations."""
        if event.type in (EventType.ADDED, EventType.UPDATED):
            self.descriptor = event.descriptor
        elif isinstance(event, UplinkEvent):
            if self.uplink is not None and event.received_at < self.uplink.received_at:
                return False
            self.uplink = event
        elif isinstance(event, JoinEvent):
            if self.join is not None and event.received_at < self.join.received_at:
                return False
            self.join = event
        elif isinstance(event, StatusEvent):
            if self.status is not None and event.received_at < self.status.received_at:
                return False
            self.status = event
        else:
            return False
        return True


class RegisteredConnection:
    """Manage a connection's registration and subscriptions."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        connection: Connection,
        configuration_url: str | None,
    ) -> None:
        """Initialize the registration."""
        self.connection = connection
        self._hass = hass
        self._entry_id = entry_id
        self._registry = hass.data[DATA_REGISTRY]
        self.configuration_url = configuration_url
        self.devices: dict[str, DeviceState] = {}
        self._active = False
        self._disconnected = False
        self._pending_discoveries: set[str] = set()
        self._unsubscribes: list[Unsubscribe] = []
        self._discovery_brands: dict[str, set[int | str]] = {}
        for domain, matchers in self._registry.integrations.items():
            brands = {
                brand_id
                for stack, brand_id in matchers
                if stack == connection.stack_type
            }
            if brands:
                self._discovery_brands[domain] = brands

    async def async_setup(self) -> None:
        """Subscribe to the connection and publish its registration."""
        self._registry.pending_connection_registrations.add(self._entry_id)
        try:
            self._unsubscribes.append(self.connection.on_disconnect(self.unsubscribe))
            self._unsubscribes.append(
                await self.connection.async_subscribe(
                    brands=None,
                    listener=self._handle_event,
                )
            )
        except BaseException:
            self.unsubscribe()
            raise
        finally:
            self._registry.pending_connection_registrations.discard(self._entry_id)

        if self._disconnected:
            self.unsubscribe()
            raise ConnectionUnavailable("Connection lost during registration")
        self._registry.connections[self._entry_id] = self
        self._active = True
        async_dispatcher_send(self._hass, SIGNAL_DEVICES_CHANGED)
        change: ConnectionChange = (self._entry_id, self.connection)
        notify(self._registry.connection_change_listeners, change)
        for domain in sorted(self._pending_discoveries):
            self._discover(domain)
        self._pending_discoveries.clear()

    @callback
    def unsubscribe(self) -> None:
        """Unregister the connection and release subscriptions."""
        self._disconnected = True
        if self._active:
            self._active = False
            self._registry.connections.pop(self._entry_id)
            self.devices.clear()
            async_dispatcher_send(self._hass, SIGNAL_DEVICES_CHANGED)
            change: ConnectionChange = (self._entry_id, None)
            notify(self._registry.connection_change_listeners, change)
        for unsubscribe in self._unsubscribes:
            unsubscribe()
        self._unsubscribes.clear()

    @callback
    def _handle_event(self, event: DeviceEvent) -> None:
        """Update device observations and discover matching integrations."""
        if self._disconnected:
            return
        if event.type == EventType.REMOVED:
            self.devices.pop(event.dev_eui, None)
        elif (state := self.devices.get(event.dev_eui)) is not None:
            if not state.receive(event):
                return
        elif event.type in (EventType.ADDED, EventType.UPDATED):
            self.devices[event.dev_eui] = DeviceState(event.descriptor)
        else:
            return
        if self._active:
            async_dispatcher_send(self._hass, SIGNAL_DEVICES_CHANGED)
        if event.type != EventType.ADDED:
            return
        brand_id = event.descriptor.brand_id
        for domain, brands in self._discovery_brands.items():
            if brand_id in brands:
                if self._active:
                    self._discover(domain)
                else:
                    self._pending_discoveries.add(domain)

    @callback
    def _discover(self, domain: str) -> None:
        """Start discovery for a device integration."""
        discovery_flow.async_create_flow(
            self._hass,
            domain,
            context={"source": SOURCE_INTEGRATION_DISCOVERY},
            data=LoRaWANDiscoveryInfo(),
        )


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
    registered = RegisteredConnection(hass, entry_id, connection, configuration_url)
    await registered.async_setup()
    return registered.unsubscribe
