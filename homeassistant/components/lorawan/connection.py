"""LoRaWAN connection handling."""

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


class RegisteredConnection:
    """Manage a connection's registration and subscriptions."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        connection: Connection,
    ) -> None:
        """Initialize the registration."""
        self.connection = connection
        self._hass = hass
        self._entry_id = entry_id
        self._registry = hass.data[DATA_REGISTRY]
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
                    brands=frozenset(
                        (self.connection.stack_type, brand_id)
                        for brands in self._discovery_brands.values()
                        for brand_id in brands
                    ),
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
            change: ConnectionChange = (self._entry_id, None)
            notify(self._registry.connection_change_listeners, change)
        for unsubscribe in self._unsubscribes:
            unsubscribe()
        self._unsubscribes.clear()

    @callback
    def _handle_event(self, event: DeviceEvent) -> None:
        """Discover matching device integrations."""
        if self._disconnected or event.type != EventType.ADDED:
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
) -> Unsubscribe:
    """Register a connected backend from lorawan-connection and return cleanup."""
    registry = hass.data[DATA_REGISTRY]
    entry_id = entry.entry_id
    if (
        entry_id in registry.connections
        or entry_id in registry.pending_connection_registrations
    ):
        raise ValueError("A connection is already registered for this entry")
    registered = RegisteredConnection(hass, entry_id, connection)
    await registered.async_setup()
    return registered.unsubscribe
