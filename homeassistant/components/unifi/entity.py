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
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription

from .const import ATTR_MANUFACTURER

if TYPE_CHECKING:
    from .controller import UniFiController

HandlerT = TypeVar("HandlerT", bound=APIHandler)
SubscriptionT = Callable[[CallbackType, ItemEvent], UnsubscribeType]


@callback
def async_device_available_fn(controller: UniFiController, obj_id: str) -> bool:
    """Check if device is available."""
    if "_" in obj_id:  # Sub device (outlet or port)
        obj_id = obj_id.partition("_")[0]

    device = controller.api.devices[obj_id]
    return controller.available and not device.disabled


@callback
def async_device_device_info_fn(api: aiounifi.Controller, obj_id: str) -> DeviceInfo:
    """Create device registry entry for device."""
    if "_" in obj_id:  # Sub device (outlet or port)
        obj_id = obj_id.partition("_")[0]

    device = api.devices[obj_id]
    return DeviceInfo(
        connections={(CONNECTION_NETWORK_MAC, device.mac)},
        manufacturer=ATTR_MANUFACTURER,
        model=device.model,
        name=device.name or None,
        sw_version=device.version,
        hw_version=str(device.board_revision),
    )


@dataclass
class UnifiDescription(Generic[HandlerT, ApiItemT]):
    """Validate and load entities from different UniFi handlers."""

    allowed_fn: Callable[[UniFiController, str], bool]
    api_handler_fn: Callable[[aiounifi.Controller], HandlerT]
    available_fn: Callable[[UniFiController, str], bool]
    device_info_fn: Callable[[aiounifi.Controller, str], DeviceInfo | None]
    event_is_on: tuple[EventKey, ...] | None
    event_to_subscribe: tuple[EventKey, ...] | None
    name_fn: Callable[[ApiItemT], str | None]
    object_fn: Callable[[aiounifi.Controller, str], ApiItemT]
    supported_fn: Callable[[UniFiController, str], bool | None]
    unique_id_fn: Callable[[UniFiController, str], str]


@dataclass
class UnifiEntityDescription(EntityDescription, UnifiDescription[HandlerT, ApiItemT]):
    """UniFi Entity Description."""


class UnifiEntity(Entity, Generic[HandlerT, ApiItemT]):
    """Representation of a UniFi entity."""

    entity_description: UnifiEntityDescription[HandlerT, ApiItemT]
    _attr_should_poll = False

    _attr_unique_id: str

    def __init__(
        self,
        obj_id: str,
        controller: UniFiController,
        description: UnifiEntityDescription[HandlerT, ApiItemT],
    ) -> None:
        """Set up UniFi switch entity."""
        self._obj_id = obj_id
        self.controller = controller
        self.entity_description = description

        controller.known_objects.add((description.key, obj_id))

        self._removed = False

        self._attr_available = description.available_fn(controller, obj_id)
        self._attr_device_info = description.device_info_fn(controller.api, obj_id)
        self._attr_unique_id = description.unique_id_fn(controller, obj_id)

        obj = description.object_fn(self.controller.api, obj_id)
        self._attr_name = description.name_fn(obj)
        self.async_initiate_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        description = self.entity_description
        handler = description.api_handler_fn(self.controller.api)

        @callback
        def unregister_object() -> None:
            """Remove object ID from known_objects when unloaded."""
            self.controller.known_objects.discard((description.key, self._obj_id))

        self.async_on_remove(unregister_object)

        # New data from handler
        self.async_on_remove(
            handler.subscribe(
                self.async_signalling_callback,
                id_filter=self._obj_id,
            )
        )

        # State change from controller or websocket
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.controller.signal_reachable,
                self.async_signal_reachable_callback,
            )
        )

        # Config entry options updated
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.controller.signal_options_update,
                self.async_signal_options_updated,
            )
        )

        # Subscribe to events if defined
        if description.event_to_subscribe is not None:
            self.async_on_remove(
                self.controller.api.events.subscribe(
                    self.async_event_callback,
                    description.event_to_subscribe,
                )
            )

    @callback
    def async_signalling_callback(self, event: ItemEvent, obj_id: str) -> None:
        """Update the entity state."""
        if event == ItemEvent.DELETED and obj_id == self._obj_id:
            self.hass.async_create_task(self.remove_item({self._obj_id}))
            return

        description = self.entity_description
        if not description.supported_fn(self.controller, self._obj_id):
            self.hass.async_create_task(self.remove_item({self._obj_id}))
            return

        self._attr_available = description.available_fn(self.controller, self._obj_id)
        self.async_update_state(event, obj_id)
        self.async_write_ha_state()

    @callback
    def async_signal_reachable_callback(self) -> None:
        """Call when controller connection state change."""
        self.async_signalling_callback(ItemEvent.ADDED, self._obj_id)

    async def async_signal_options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        if not self.entity_description.allowed_fn(self.controller, self._obj_id):
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
        raise NotImplementedError()
