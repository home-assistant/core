"""UniFi entity representation."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, TypeVar

import aiounifi
from aiounifi.interfaces.api_handlers import (
    APIHandler,
    CallbackType,
    ItemEvent,
    UnsubscribeType,
)
from aiounifi.models.api import ApiItemT
from aiounifi.models.event import Event, EventKey

from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceEntryType,
    DeviceInfo,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import ATTR_MANUFACTURER, DOMAIN

if TYPE_CHECKING:
    from .hub import UnifiHub

HandlerT = TypeVar("HandlerT", bound=APIHandler)
SubscriptionT = Callable[[CallbackType, ItemEvent], UnsubscribeType]


@callback
def async_device_available_fn(hub: UnifiHub, obj_id: str) -> bool:
    """Check if device is available."""
    if "_" in obj_id:  # Sub device (outlet or port)
        obj_id = obj_id.partition("_")[0]

    device = hub.api.devices[obj_id]
    return hub.available and not device.disabled


@callback
def async_wlan_available_fn(hub: UnifiHub, obj_id: str) -> bool:
    """Check if WLAN is available."""
    wlan = hub.api.wlans[obj_id]
    return hub.available and wlan.enabled


@callback
def async_device_device_info_fn(hub: UnifiHub, obj_id: str) -> DeviceInfo:
    """Create device registry entry for device."""
    if "_" in obj_id:  # Sub device (outlet or port)
        obj_id = obj_id.partition("_")[0]

    device = hub.api.devices[obj_id]
    return DeviceInfo(
        connections={(CONNECTION_NETWORK_MAC, device.mac)},
        manufacturer=ATTR_MANUFACTURER,
        model=device.model,
        name=device.name or None,
        sw_version=device.version,
        hw_version=str(device.board_revision),
    )


@callback
def async_wlan_device_info_fn(hub: UnifiHub, obj_id: str) -> DeviceInfo:
    """Create device registry entry for WLAN."""
    wlan = hub.api.wlans[obj_id]
    return DeviceInfo(
        entry_type=DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, wlan.id)},
        manufacturer=ATTR_MANUFACTURER,
        model="UniFi WLAN",
        name=wlan.name,
    )


@callback
def async_client_device_info_fn(hub: UnifiHub, obj_id: str) -> DeviceInfo:
    """Create device registry entry for client."""
    client = hub.api.clients[obj_id]
    return DeviceInfo(
        connections={(CONNECTION_NETWORK_MAC, obj_id)},
        default_manufacturer=client.oui,
        default_name=client.name or client.hostname,
    )


@dataclass(frozen=True, kw_only=True)
class UnifiEntityDescription(EntityDescription, Generic[HandlerT, ApiItemT]):
    """UniFi Entity Description."""

    api_handler_fn: Callable[[aiounifi.Controller], HandlerT]
    """Provide api_handler from api."""
    device_info_fn: Callable[[UnifiHub, str], DeviceInfo | None]
    """Provide device info object based on hub and obj_id."""
    object_fn: Callable[[aiounifi.Controller, str], ApiItemT]
    """Retrieve object based on api and obj_id."""
    unique_id_fn: Callable[[UnifiHub, str], str]
    """Provide a unique ID based on hub and obj_id."""

    # Optional functions
    allowed_fn: Callable[[UnifiHub, str], bool] = lambda hub, obj_id: True
    """Determine if config entry options allow creation of entity."""
    available_fn: Callable[[UnifiHub, str], bool] = lambda hub, obj_id: hub.available
    """Determine if entity is available, default is if connection is working."""
    name_fn: Callable[[ApiItemT], str | None] = lambda obj: None
    """Entity name function, can be used to extend entity name beyond device name."""
    supported_fn: Callable[[UnifiHub, str], bool] = lambda hub, obj_id: True
    """Determine if UniFi object supports providing relevant data for entity."""

    # Optional constants
    has_entity_name = True  # Part of EntityDescription
    """Has entity name defaults to true."""
    event_is_on: set[EventKey] | None = None
    """Which UniFi events should be used to consider state 'on'."""
    event_to_subscribe: tuple[EventKey, ...] | None = None
    """Which UniFi events to listen on."""
    should_poll: bool = False
    """If entity needs to do regular checks on state."""


class UnifiEntity(Entity, Generic[HandlerT, ApiItemT]):
    """Representation of a UniFi entity."""

    entity_description: UnifiEntityDescription[HandlerT, ApiItemT]
    _attr_unique_id: str

    def __init__(
        self,
        obj_id: str,
        hub: UnifiHub,
        description: UnifiEntityDescription[HandlerT, ApiItemT],
    ) -> None:
        """Set up UniFi switch entity."""
        self._obj_id = obj_id
        self.hub = hub
        self.api = hub.api
        self.entity_description = description

        hub.entity_loader.known_objects.add((description.key, obj_id))

        self._removed = False

        self._attr_available = description.available_fn(hub, obj_id)
        self._attr_device_info = description.device_info_fn(hub, obj_id)
        self._attr_should_poll = description.should_poll
        self._attr_unique_id = description.unique_id_fn(hub, obj_id)

        obj = description.object_fn(self.api, obj_id)
        self._attr_name = description.name_fn(obj)
        self.async_initiate_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        description = self.entity_description
        handler = description.api_handler_fn(self.api)

        @callback
        def unregister_object() -> None:
            """Remove object ID from known_objects when unloaded."""
            self.hub.entity_loader.known_objects.discard(
                (description.key, self._obj_id)
            )

        self.async_on_remove(unregister_object)

        # New data from handler
        self.async_on_remove(
            handler.subscribe(
                self.async_signalling_callback,
                id_filter=self._obj_id,
            )
        )

        # State change from hub or websocket
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.hub.signal_reachable,
                self.async_signal_reachable_callback,
            )
        )

        # Config entry options updated
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.hub.signal_options_update,
                self.async_signal_options_updated,
            )
        )

        # Subscribe to events if defined
        if description.event_to_subscribe is not None:
            self.async_on_remove(
                self.api.events.subscribe(
                    self.async_event_callback,
                    description.event_to_subscribe,
                )
            )

    @callback
    def async_signalling_callback(self, event: ItemEvent, obj_id: str) -> None:
        """Update the entity state."""
        if event is ItemEvent.DELETED and obj_id == self._obj_id:
            self.hass.async_create_task(self.remove_item({obj_id}))
            return

        description = self.entity_description
        if not description.supported_fn(self.hub, self._obj_id):
            self.hass.async_create_task(self.remove_item({self._obj_id}))
            return

        self._attr_available = description.available_fn(self.hub, self._obj_id)
        self.async_update_state(event, obj_id)
        self.async_write_ha_state()

    @callback
    def async_signal_reachable_callback(self) -> None:
        """Call when hub connection state change."""
        self.async_signalling_callback(ItemEvent.ADDED, self._obj_id)

    async def async_signal_options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        if not self.entity_description.allowed_fn(self.hub, self._obj_id):
            await self.remove_item({self._obj_id})

    async def remove_item(self, keys: set) -> None:
        """Remove entity if object ID is part of set."""
        if self._obj_id not in keys or self._removed:
            return
        self._removed = True
        if self.registry_entry:
            er.async_get(self.hass).async_remove(self.entity_id)
        else:
            await self.async_remove(force_remove=True)

    async def async_update(self) -> None:
        """Update state if polling is configured."""
        self.async_update_state(ItemEvent.CHANGED, self._obj_id)

    @callback
    def async_initiate_state(self) -> None:
        """Initiate entity state.

        Perform additional actions setting up platform entity child class state.
        Defaults to using async_update_state to set initial state.
        """
        self.async_update_state(ItemEvent.ADDED, self._obj_id)

    @callback
    @abstractmethod
    def async_update_state(self, event: ItemEvent, obj_id: str) -> None:
        """Update entity state.

        Perform additional actions updating platform entity child class state.
        """

    @callback
    def async_event_callback(self, event: Event) -> None:
        """Update entity state based on subscribed event.

        Perform additional action updating platform entity child class state.
        """
        raise NotImplementedError
