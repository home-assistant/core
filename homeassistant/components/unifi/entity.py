"""UniFi entity representation."""

from abc import abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import time
from functools import partial
from typing import TYPE_CHECKING, Any, Literal, override

import aiounifi
from aiounifi.interfaces.api_handlers import (
    APIHandler,
    CallbackType,
    ItemEvent,
    UnsubscribeType,
)
from aiounifi.models.api import ApiItem
from aiounifi.models.event import Event, EventKey
from aiounifi.models.firewall_policy import (
    FirewallPolicySchedule,
    FirewallPolicyScheduleError,
    FirewallPolicyScheduleMode,
    ScheduleDatesOutOfOrderError,
    ScheduleSettingUnusedError,
    build_schedule,
)

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    ChildDeviceInfo,
    DeviceEntryType,
    DeviceInfo,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.util import dt as dt_util

from .const import ATTR_MANUFACTURER, DOMAIN
from .coordinator import UnifiDataUpdateCoordinator

if TYPE_CHECKING:
    from .hub import UnifiHub

type SubscriptionType = Callable[[CallbackType, ItemEvent], UnsubscribeType]


def is_locally_administered_mac(mac: str) -> bool:
    """Return True if the MAC has the locally-administered (U/L) bit set."""
    return bool(int(mac.split(":", 1)[0], 16) & 0x02)


@callback
def async_client_ssid_allowed_fn(hub: UnifiHub, obj_id: str) -> bool:
    """Check if client is connected to an allowed SSID."""
    client = hub.api.clients[obj_id]

    is_wireless = hub.entity_loader.wireless_clients.is_wireless(client)

    return not (
        is_wireless
        and client.essid
        and hub.config.option_ssid_filter
        and client.essid not in hub.config.option_ssid_filter
    )


@callback
def async_device_available_fn(hub: UnifiHub, obj_id: str) -> bool:
    """Check if device is available."""
    if "_" in obj_id:  # Sub device (outlet or port)
        obj_id = obj_id.partition("_")[0]

    device = hub.api.devices[obj_id]
    return hub.available and not device.disabled


@callback
def async_device_supported_fn(hub: UnifiHub, obj_id: str) -> bool:
    """Check if device is adopted by the controller.

    The controller also lists devices that are only pending adoption,
    like a neighbour's access point. Those are not part of the site.
    """
    if "_" in obj_id:  # Sub device (outlet or port)
        obj_id = obj_id.partition("_")[0]

    return hub.api.devices[obj_id].raw.get("adopted", True)


@callback
def async_port_poe_supported_fn(hub: UnifiHub, obj_id: str) -> bool:
    """Check if port supports PoE."""
    return async_device_supported_fn(hub, obj_id) and bool(
        hub.api.ports[obj_id].port_poe
    )


@callback
def async_firewall_policy_supported_fn(hub: UnifiHub, obj_id: str) -> bool:
    """Check if firewall policy can be controlled."""
    policy = hub.api.firewall_policies[obj_id]
    return not policy.predefined and policy.name != ""


SCHEDULE_ERROR_TRANSLATION_KEYS: dict[type[FirewallPolicyScheduleError], str] = {
    ScheduleDatesOutOfOrderError: "schedule_dates_out_of_order",
    ScheduleSettingUnusedError: "schedule_setting_unused_in_mode",
}


async def async_save_firewall_policy_schedule(
    hub: UnifiHub,
    obj_id: str,
    *,
    mode: FirewallPolicyScheduleMode | None = None,
    start_time: time | None = None,
    end_time: time | None = None,
) -> None:
    """Save a change to a firewall policy's schedule.

    "Today" is the controller's date: its clock is the one the schedule runs on.
    """

    def schedule_fn(current: Mapping[str, Any]) -> FirewallPolicySchedule:
        try:
            return build_schedule(
                current,
                dt_util.now(hub.time_zone).date(),
                mode=mode,
                start_time=start_time,
                end_time=end_time,
            )
        except FirewallPolicyScheduleError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key=SCHEDULE_ERROR_TRANSLATION_KEYS[type(err)],
            ) from err

    await hub.async_save_firewall_policy(obj_id, schedule_fn=schedule_fn)


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
        name=device.name or device.model,
        sw_version=device.version,
        hw_version=str(device.board_revision),
    )


@callback
def async_child_device_info_fn(
    hub: UnifiHub, obj_id: str, *, kind: Literal["port", "outlet"]
) -> ChildDeviceInfo:
    """Create device information for a port or outlet."""
    registry = dr.async_get(hub.hass)
    parent = registry.async_get_device_by_connection(
        (CONNECTION_NETWORK_MAC, obj_id.partition("_")[0]),
        hub.config.entry.entry_id,
    )
    if parent is None:
        parent = registry.async_get_or_create_from_info(
            config_entry_id=hub.config.entry.entry_id,
            device_info=async_device_device_info_fn(hub, obj_id),
        )
    child_info = ChildDeviceInfo(
        identifiers={(DOMAIN, f"{kind}-{obj_id}")},
        parent_device_id=parent.id,
    )
    if kind == "port":
        child_info.name = hub.api.ports[obj_id].name
    elif (outlet := hub.api.outlets[obj_id]).name:
        child_info.name = outlet.name
    else:
        child_info.translation_key = "outlet"
        child_info.translation_placeholders = {"index": str(outlet.index)}
    return child_info


async_port_device_info_fn = partial(async_child_device_info_fn, kind="port")
async_outlet_device_info_fn = partial(async_child_device_info_fn, kind="outlet")


FIREWALL_POLICY_DEVICE_PREFIX = "firewall_policy-"


@callback
def async_firewall_policy_id_of_device(device: dr.ChildDeviceEntry) -> str | None:
    """Return the ID of the firewall policy a child device was created for."""
    for domain, identifier in device.identifiers:
        if domain == DOMAIN and identifier.startswith(FIREWALL_POLICY_DEVICE_PREFIX):
            return identifier.removeprefix(FIREWALL_POLICY_DEVICE_PREFIX)
    return None


@callback
def async_firewall_policy_device_info_fn(hub: UnifiHub, obj_id: str) -> ChildDeviceInfo:
    """Create device information for a firewall policy."""
    registry = dr.async_get(hub.hass)
    parent = registry.async_get_or_create_from_info(
        config_entry_id=hub.config.entry.entry_id,
        device_info=async_unifi_network_device_info_fn(hub, obj_id),
    )
    return ChildDeviceInfo(
        identifiers={(DOMAIN, f"{FIREWALL_POLICY_DEVICE_PREFIX}{obj_id}")},
        name=hub.api.firewall_policies[obj_id].name,
        parent_device_id=parent.id,
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
        manufacturer=client.oui,
        name=client.name or client.hostname,
    )


@callback
def async_unifi_network_device_info_fn(hub: UnifiHub, obj_id: str) -> DeviceInfo:
    """Create device registry entry for the UniFi Network application."""
    unique_id = hub.config.entry.unique_id
    assert unique_id is not None
    return DeviceInfo(
        entry_type=DeviceEntryType.SERVICE,
        identifiers={(SWITCH_DOMAIN, unique_id)},
        manufacturer=ATTR_MANUFACTURER,
        model="UniFi Network",
        name="UniFi Network",
    )


@dataclass(frozen=True, kw_only=True)
class UnifiEntityDescription[HandlerT: APIHandler, ItemT: ApiItem](EntityDescription):
    """UniFi Entity Description."""

    api_handler_fn: Callable[[aiounifi.Controller], HandlerT]
    """Provide api_handler from api."""
    device_info_fn: Callable[[UnifiHub, str], DeviceInfo | ChildDeviceInfo | None]
    """Provide device info object based on hub and obj_id."""
    object_fn: Callable[[aiounifi.Controller, str], ItemT]
    """Retrieve object based on api and obj_id."""
    unique_id_fn: Callable[[UnifiHub, str], str]
    """Provide a unique ID based on hub and obj_id."""

    # Optional functions
    allowed_fn: Callable[[UnifiHub, str], bool] = lambda hub, obj_id: True
    """Determine if config entry options allow creation of entity."""
    available_fn: Callable[[UnifiHub, str], bool] = lambda hub, obj_id: hub.available
    """Determine if entity is available, default is if connection is working."""
    name_fn: Callable[[ItemT], str | None] = lambda obj: None
    """Entity name function, can be used to extend entity name beyond device name."""
    supported_fn: Callable[[UnifiHub, str], bool] = lambda hub, obj_id: True
    """Determine if UniFi object supports providing relevant data for entity."""
    translation_placeholders_fn: Callable[[ItemT], Mapping[str, str]] | None = None
    """Provide translation placeholders used together with translation_key."""

    # Optional constants
    has_entity_name = True  # Part of EntityDescription
    """Has entity name defaults to true."""
    event_is_on: set[EventKey] | None = None
    """Which UniFi events should be used to consider state 'on'."""
    event_to_subscribe: tuple[EventKey, ...] | None = None
    """Which UniFi events to listen on."""
    should_poll: bool = False
    """If entity needs to do regular checks on state."""


class UnifiEntity[HandlerT: APIHandler, ItemT: ApiItem](Entity):
    """Representation of a UniFi entity."""

    entity_description: UnifiEntityDescription[HandlerT, ItemT]
    coordinator: UnifiDataUpdateCoordinator[HandlerT]
    _attr_unique_id: str

    def __init__(
        self,
        obj_id: str,
        hub: UnifiHub,
        description: UnifiEntityDescription[HandlerT, ItemT],
    ) -> None:
        """Set up UniFi switch entity."""
        self._obj_id = obj_id
        self.hub = hub
        self.api = hub.api
        self.entity_description = description
        self.coordinator = hub.entity_loader.get_data_update_coordinator(
            description.api_handler_fn(self.api)
        )

        hub.entity_loader.known_objects.add((description.key, obj_id))

        self._removed = False

        self._attr_available = description.available_fn(hub, obj_id)
        self._attr_device_info = description.device_info_fn(hub, obj_id)
        self._attr_should_poll = description.should_poll
        self._attr_unique_id = description.unique_id_fn(hub, obj_id)

        obj = description.object_fn(self.api, obj_id)
        if (name := description.name_fn(obj)) is not None:
            self._attr_name = name
        if description.translation_placeholders_fn is not None:
            self._attr_translation_placeholders = (
                description.translation_placeholders_fn(obj)
            )
        self.async_initiate_state()

    @property
    @override
    def available(self) -> bool:
        """Return whether the entity and its coordinator are available."""
        return super().available and self.coordinator.last_update_success

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        description = self.entity_description

        @callback
        def unregister_object() -> None:
            """Remove object ID from known_objects when unloaded."""
            self.hub.entity_loader.known_objects.discard(
                (description.key, self._obj_id)
            )

        self.async_on_remove(unregister_object)

        # New data from coordinator
        self.async_on_remove(
            self.coordinator.async_add_listener(
                self._async_coordinator_updated,
                context=(self._obj_id, self._obj_id.partition("_")[0]),
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
    @override
    def add_to_platform_abort(self) -> None:
        """Keep the object of a disabled entity known, forget any other.

        A disabled entity is not added but keeps its registry entry, so its
        object stays known until that entry is removed. Any other entity
        that is not added is tried again on the next scan.
        """
        super().add_to_platform_abort()
        loader = self.hub.entity_loader
        obj = (self.entity_description.key, self._obj_id)
        if (entry := self.registry_entry) and entry.disabled:
            loader.known_but_disabled[entry.entity_id] = obj
        else:
            loader.known_objects.discard(obj)

    @callback
    def _async_coordinator_updated(self) -> None:
        """Skip coordinator updates that changed a different object."""
        coordinator_data = self.coordinator.data
        if coordinator_data is None and self.coordinator.supports_websocket:
            self.async_write_ha_state()
            return
        if coordinator_data is None:
            event = ItemEvent.CHANGED
            changed_obj_id = None
        else:
            event, changed_obj_id = coordinator_data

        own_obj_id = self._obj_id.partition("_")[0]
        if changed_obj_id is not None and changed_obj_id not in (
            self._obj_id,
            own_obj_id,
        ):
            return
        self._async_process_update(event)

    @callback
    def _async_process_update(self, event: ItemEvent = ItemEvent.CHANGED) -> None:
        """Update the entity state from the handler."""
        handler = self.entity_description.api_handler_fn(self.api)
        if self._obj_id not in handler:
            self.hass.async_create_task(self.remove_item({self._obj_id}))
            return

        description = self.entity_description
        if not description.supported_fn(self.hub, self._obj_id):
            self.hub.adoption.async_follow_if_unadopted(self._obj_id)
            self.hass.async_create_task(self.remove_item({self._obj_id}))
            return

        self._attr_available = description.available_fn(self.hub, self._obj_id)
        self.async_update_state(event, self._obj_id)
        self.async_write_ha_state()

    @callback
    def async_signalling_callback(self, event: ItemEvent, obj_id: str) -> None:
        """Update the entity state from a handler event."""
        if event is ItemEvent.DELETED and obj_id == self._obj_id:
            self.hass.async_create_task(self.remove_item({obj_id}))
            return

        self._async_process_update(event)

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

    async def async_refresh_after_control(self) -> None:
        """Refresh handler data after a control call when polling."""
        if (
            not self.coordinator.supports_websocket
            and self.coordinator.update_interval is not None
        ):
            await self.coordinator.async_refresh()

    @callback
    def async_initiate_state(self) -> None:
        """Initiate entity state.

        Perform additional actions setting up platform entity child class state.
        Defaults to using async_update_state to set initial state.
        """
        self.async_update_state(ItemEvent.ADDED, self._obj_id)

    @callback
    def get_object(self) -> ItemT:
        """Return the latest object for this entity."""
        return self.entity_description.object_fn(self.api, self._obj_id)

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
