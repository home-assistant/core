"""Manage vendor models and coordinators across registered LoRaWAN connections."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
import logging
from typing import Any

from lorawan_connection import (
    AddedEvent,
    Connection,
    ConnectionUnavailable,
    Device,
    DeviceCollection,
    DeviceDescriptor,
    DeviceEvent,
    Downlink,
    DownlinkError,
    EventType,
    RemovedEvent,
    Unsubscribe,
    UpdatedEvent,
    notify,
    subscribe,
)

from homeassistant.config_entries import (
    SIGNAL_CONFIG_ENTRY_CHANGED,
    ConfigEntry,
    ConfigEntryChange,
)
from homeassistant.core import HomeAssistant, callback as hass_callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .connection import DATA_REGISTRY, RegisteredConnection

_LOGGER = logging.getLogger(__name__)


def device_identifier(domain: str, device: Device) -> tuple[str, str]:
    """Build device registry identifier from the integration domain, network ID and DevEUI."""
    descriptor = device.descriptor
    return (domain, f"{descriptor.network_id}:{descriptor.dev_eui}")


class _CollectionConnection:
    """Keep one collection subscribed while its server transport is replaced."""

    def __init__(self) -> None:
        self.registration: RegisteredConnection | None = None
        self._devices: dict[str, DeviceDescriptor] = {}
        self._unsubscribe: Unsubscribe | None = None
        self._listeners: list[
            tuple[
                frozenset[tuple[str, int | str]] | None, Callable[[DeviceEvent], None]
            ]
        ] = []
        self._disconnect: list[Callable[[None], None]] = []

    async def async_subscribe(
        self,
        *,
        brands: frozenset[tuple[str, int | str]] | None,
        callback: Callable[[DeviceEvent], None],
    ) -> Unsubscribe:
        item = (brands, callback)
        self._listeners.append(item)
        for descriptor in tuple(self._devices.values()):
            if brands is None or (descriptor.stack, descriptor.brand_id) in brands:
                callback(self._event(EventType.ADDED, descriptor))

        def unsubscribe() -> None:
            if item in self._listeners:
                self._listeners.remove(item)

        return unsubscribe

    def on_disconnect(self, callback: Callable[[], None]) -> Unsubscribe:
        return subscribe(self._disconnect, lambda _: callback())

    async def async_send_downlink(self, downlink: Downlink) -> str:
        if self.registration is None:
            raise DownlinkError("LoRaWAN connection is unavailable")
        return await self.registration.connection.async_send_downlink(downlink)

    def detach(self) -> None:
        self.registration = None
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        notify(self._disconnect, None)

    async def attach(self, registration: RegisteredConnection) -> None:
        self.registration = registration
        previous = dict(self._devices)
        seen: set[str] = set()

        def receive(event: DeviceEvent) -> None:
            if self.registration is not registration:
                return
            if event.type == EventType.REMOVED:
                seen.discard(event.dev_eui)
            else:
                seen.add(event.dev_eui)
            self.emit(event)

        brands = (
            None
            if any(brands is None for brands, _ in self._listeners)
            else frozenset(
                pair
                for brands, _ in self._listeners
                if brands is not None
                for pair in brands
            )
        )
        unsubscribe = await registration.connection.async_subscribe(
            brands=brands, callback=receive
        )
        if self.registration is not registration:
            unsubscribe()
            return
        self._unsubscribe = unsubscribe
        for eui, descriptor in previous.items():
            if eui not in seen:
                self.emit(self._event(EventType.REMOVED, descriptor))

    @staticmethod
    def _event(kind: EventType, descriptor: DeviceDescriptor) -> DeviceEvent:
        event_classes: dict[
            EventType, type[AddedEvent | UpdatedEvent | RemovedEvent]
        ] = {
            EventType.ADDED: AddedEvent,
            EventType.UPDATED: UpdatedEvent,
            EventType.REMOVED: RemovedEvent,
        }
        return event_classes[kind](descriptor=descriptor, received_at=dt_util.utcnow())

    def emit(self, event: DeviceEvent) -> None:
        previous = self._devices.get(event.dev_eui)
        descriptor = event.descriptor or previous
        if descriptor is None:
            return
        if event.type == EventType.REMOVED:
            self._devices.pop(event.dev_eui, None)
        else:
            self._devices[event.dev_eui] = descriptor
        for brands, listener in tuple(self._listeners):
            if brands is None or (descriptor.stack, descriptor.brand_id) in brands:
                notify([listener], event)
            elif previous and (previous.stack, previous.brand_id) in brands:
                notify([listener], self._event(EventType.REMOVED, previous))


@dataclass
class _Session[DeviceT: Device]:
    connection: _CollectionConnection
    collection: DeviceCollection[DeviceT]
    unsubscribes: list[Unsubscribe] = field(default_factory=list)


class DeviceManager[DeviceT: Device, CoordinatorT: DataUpdateCoordinator[Any]]:
    """Own one collection per server and share its models through coordinators.

    Subscribe to current and future registered connections. Keep models and
    entities on temporary disconnection; reconcile removals when a server returns.
    Remove registry records when devices or their server config entry are deleted.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        *,
        create_collection: Callable[[Connection], DeviceCollection[DeviceT]],
        create_coordinator: Callable[[HomeAssistant, DeviceT], CoordinatorT],
    ) -> None:
        """Store collection and coordinator factories for every connection."""
        self.coordinators: dict[tuple[str, str], CoordinatorT] = {}
        self._hass = hass
        self._entry = entry
        self._registry = dr.async_get(hass)
        self._create_collection = create_collection
        self._create_coordinator = create_coordinator
        self._sessions: dict[str, _Session[DeviceT]] = {}
        self._listeners: list[Callable[[CoordinatorT], None]] = []
        self._unsubscribes: list[Unsubscribe] = []
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._closed = False
        self._started = False

    async def async_setup(self) -> None:
        """Subscribe to all current and future connections without selecting a server."""
        if self._closed or self._started:
            raise RuntimeError("Device manager is closed or already set up")
        self._started = True
        registry = self._hass.data[DATA_REGISTRY]
        self._unsubscribes.extend(
            [
                subscribe(
                    registry.changed, lambda change: self._connection_changed(change[0])
                ),
                async_dispatcher_connect(
                    self._hass, SIGNAL_CONFIG_ENTRY_CHANGED, self._entry_changed
                ),
            ]
        )
        try:
            for entry_id in tuple(registry.connections):
                await self._async_attach(entry_id)
        except BaseException:
            self.close()
            raise
        self._cleanup_deleted_connections()

    @hass_callback
    def _connection_changed(self, entry_id: str) -> None:
        if task := self._tasks.pop(entry_id, None):
            task.cancel()
        if entry_id not in self._hass.data[DATA_REGISTRY].connections:
            if session := self._sessions.get(entry_id):
                session.connection.detach()
                for key, coordinator in tuple(self.coordinators.items()):
                    if key[0] == entry_id:
                        coordinator.async_set_update_error(
                            ConnectionUnavailable("LoRaWAN connection is unavailable")
                        )
            return
        self._tasks[entry_id] = self._entry.async_create_task(
            self._hass, self._async_attach(entry_id), "Attach LoRaWAN connection"
        )

    async def _async_attach(self, entry_id: str) -> None:
        registration = self._hass.data[DATA_REGISTRY].connections.get(entry_id)
        if registration is None or self._closed:
            return
        session = self._sessions.get(entry_id)
        if session is None:
            connection = _CollectionConnection()
            collection = self._create_collection(connection)
            session = self._sessions[entry_id] = _Session(connection, collection)
            session.unsubscribes.extend(
                [
                    collection.subscribe_device_added(
                        lambda device: self._device_added(entry_id, device)
                    ),
                    collection.subscribe_device_removed(
                        lambda device: self._device_removed(entry_id, device)
                    ),
                ]
            )
            try:
                await collection.async_setup()
            except BaseException:
                self._close_session(entry_id)
                raise
        try:
            await session.connection.attach(registration)
        except BaseException:
            self._close_session(entry_id)
            raise
        if (
            self._closed
            or self._hass.data[DATA_REGISTRY].connections.get(entry_id)
            is not registration
        ):
            self._connection_changed(entry_id)
            return
        current = {(entry_id, eui) for eui in session.collection.devices}
        if current != {key for key in self.coordinators if key[0] == entry_id}:
            raise HomeAssistantError("Failed to create a LoRaWAN device coordinator")
        for key in current:
            coordinator = self.coordinators[key]
            coordinator.async_set_updated_data(coordinator.data)
        identifiers = {
            device_identifier(self._entry.domain, device)
            for device in session.collection.devices.values()
        }
        for registered in dr.async_entries_for_config_entry(
            self._registry, self._entry.entry_id
        ):
            if any(
                domain == self._entry.domain and value.startswith(f"{entry_id}:")
                for domain, value in registered.identifiers
            ) and not registered.identifiers.intersection(identifiers):
                self._registry.async_remove_device(registered.id)

    @hass_callback
    def _entry_changed(self, change: ConfigEntryChange, entry: ConfigEntry) -> None:
        if change is ConfigEntryChange.REMOVED:
            if task := self._tasks.pop(entry.entry_id, None):
                task.cancel()
            self._close_session(entry.entry_id)
            self._cleanup_deleted_connections()

    def _cleanup_deleted_connections(self) -> None:
        for registered in dr.async_entries_for_config_entry(
            self._registry, self._entry.entry_id
        ):
            connection_ids = {
                value.partition(":")[0]
                for domain, value in registered.identifiers
                if domain == self._entry.domain
            }
            if connection_ids and all(
                self._hass.config_entries.async_get_entry(connection_id) is None
                for connection_id in connection_ids
            ):
                self._registry.async_remove_device(registered.id)

    @hass_callback
    def subscribe_coordinator_added(
        self, listener: Callable[[CoordinatorT], None]
    ) -> Unsubscribe:
        """Get notified when a new coordinator for a device has been added.

        Existing coordinators are delivered immediately on subscription.
        """
        if self._closed:
            raise RuntimeError("Device manager is closed")
        self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        try:
            for key, coordinator in tuple(self.coordinators.items()):
                if self.coordinators.get(key) is coordinator:
                    listener(coordinator)
        except BaseException:
            unsubscribe()
            raise
        return unsubscribe

    @hass_callback
    def _device_added(self, entry_id: str, device: DeviceT) -> None:
        coordinator = self._create_coordinator(self._hass, device)
        self.coordinators[(entry_id, device.descriptor.dev_eui)] = coordinator
        self._registry.async_get_or_create(
            config_entry_id=self._entry.entry_id,
            identifiers={device_identifier(self._entry.domain, device)},
            name=device.descriptor.name,
        )
        device.add_update_listener(lambda: self._update_name(device))
        device.add_remove_listener(lambda: self._remove_registry_device(device))
        notify(self._listeners, coordinator)

    def _registry_device(self, device: DeviceT) -> dr.DeviceEntry | None:
        return self._registry.async_get_device_by_identifier(
            device_identifier(self._entry.domain, device), self._entry.entry_id
        )

    @hass_callback
    def _update_name(self, device: DeviceT) -> None:
        if registered := self._registry_device(device):
            self._registry.async_update_device(
                registered.id, name=device.descriptor.name
            )

    @hass_callback
    def _remove_registry_device(self, device: DeviceT) -> None:
        if registered := self._registry_device(device):
            self._registry.async_remove_device(registered.id)

    @hass_callback
    def _device_removed(self, entry_id: str, device: DeviceT) -> None:
        if coordinator := self.coordinators.pop(
            (entry_id, device.descriptor.dev_eui), None
        ):
            self._entry.async_create_task(
                self._hass,
                coordinator.async_shutdown(),
                "Stop LoRaWAN device coordinator",
            )

    def _close_session(self, entry_id: str) -> None:
        if session := self._sessions.pop(entry_id, None):
            session.connection.detach()
            session.collection.close()
            for unsubscribe in session.unsubscribes:
                unsubscribe()

    @hass_callback
    def close(self) -> None:
        """Release collections, coordinators and subscriptions without deleting devices."""
        if self._closed:
            return
        self._closed = True
        for unsubscribe in reversed(self._unsubscribes):
            unsubscribe()
        self._unsubscribes.clear()
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()
        for entry_id in tuple(self._sessions):
            self._close_session(entry_id)
        self._listeners.clear()
