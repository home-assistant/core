"""Track both clients and devices using UniFi Network."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any, override

import aiounifi
from aiounifi.interfaces.api_handlers import ItemEvent
from aiounifi.interfaces.clients import Clients
from aiounifi.interfaces.devices import Devices
from aiounifi.models.api import ApiItem
from aiounifi.models.client import Client
from aiounifi.models.device import Device
from aiounifi.models.event import Event, EventKey
from aiounifi.network.v1.interfaces.clients import Clients as NetworkClients
from aiounifi.network.v1.interfaces.devices import Devices as NetworkDevices
from aiounifi.network.v1.models.client import (
    Client as NetworkClient,
    ClientType as NetworkClientType,
)
from aiounifi.network.v1.models.device import (
    Device as NetworkDevice,
    DeviceState as NetworkDeviceState,
)
from propcache.api import cached_property

from homeassistant.components.device_tracker import (
    ScannerEntity,
    ScannerEntityDescription,
)
from homeassistant.core import Event as core_Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import UnifiConfigEntry
from .const import CLIENT_TYPE_OPTION, DOMAIN, NETWORK_MIN_DETECTION_TIME
from .coordinator import UnifiApiHandler
from .entity import (
    UnifiEntity,
    UnifiEntityDescription,
    async_client_device_info_fn,
    async_client_ssid_allowed_fn,
    async_device_available_fn,
    async_device_device_info_fn,
    async_device_supported_fn,
    async_network_client_device_info_fn,
    async_network_device_device_info_fn,
    async_network_device_supported_fn,
    is_locally_administered_mac,
)
from .hub import UnifiHub

LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0

# Devices are polled through the Integration API, allow a missed poll
NETWORK_DEVICE_HEARTBEAT = timedelta(seconds=60)

CLIENT_TRACKER = "client"
DEVICE_TRACKER = "device"

CLIENT_CONNECTED_ATTRIBUTES = [
    "_is_guest_by_uap",
    "ap_mac",
    "authorized",
    "essid",
    "ip",
    "is_11r",
    "is_guest",
    "note",
    "qos_policy_applied",
    "radio",
    "radio_proto",
    "vlan",
]

CLIENT_STATIC_ATTRIBUTES = [
    "mac",
    "name",
    "oui",
]


CLIENT_CONNECTED_ALL_ATTRIBUTES = CLIENT_CONNECTED_ATTRIBUTES + CLIENT_STATIC_ATTRIBUTES

WIRED_CONNECTION = (EventKey.WIRED_CLIENT_CONNECTED,)
WIRED_DISCONNECTION = (EventKey.WIRED_CLIENT_DISCONNECTED,)
WIRELESS_CONNECTION = (
    EventKey.WIRELESS_CLIENT_CONNECTED,
    EventKey.WIRELESS_CLIENT_ROAM,
    EventKey.WIRELESS_CLIENT_ROAM_RADIO,
    EventKey.WIRELESS_GUEST_CONNECTED,
    EventKey.WIRELESS_GUEST_ROAM,
    EventKey.WIRELESS_GUEST_ROAM_RADIO,
)
WIRELESS_DISCONNECTION = (
    EventKey.WIRELESS_CLIENT_DISCONNECTED,
    EventKey.WIRELESS_GUEST_DISCONNECTED,
)


@callback
def async_client_allowed_fn(hub: UnifiHub, obj_id: str) -> bool:
    """Check if client is allowed."""
    if not async_client_ssid_allowed_fn(hub, obj_id):
        return False

    if obj_id in hub.config.option_supported_clients:
        return True

    if not hub.config.option_track_clients:
        return False

    client = hub.api.clients[obj_id]

    if (
        hub.config.option_ignore_local_mac
        and not client.is_wired
        and is_locally_administered_mac(client.mac)
    ):
        return False

    if client.mac not in hub.entity_loader.wireless_clients:
        if not hub.config.option_track_wired_clients:
            return False

    return True


@callback
def async_client_is_connected_fn(hub: UnifiHub, obj_id: str) -> bool:
    """Check if device object is disabled."""
    client = hub.api.clients[obj_id]

    if hub.entity_loader.wireless_clients.is_wireless(client) and client.is_wired:
        if not hub.config.option_ignore_wired_bug:
            return False  # Wired bug in action

    if (
        not client.is_wired
        and client.essid
        and hub.config.option_ssid_filter
        and client.essid not in hub.config.option_ssid_filter
    ):
        return False

    if (
        dt_util.utcnow() - dt_util.utc_from_timestamp(client.last_seen or 0)
        > hub.config.option_detection_time
    ):
        return False

    return True


@callback
def async_network_client_allowed_fn(hub: UnifiHub, obj_id: str) -> bool:
    """Check if a client of the Integration API is allowed."""
    if obj_id in hub.config.option_supported_clients:
        return True

    if not hub.config.option_track_clients:
        return False

    if hub.api.network.clients[obj_id].type is NetworkClientType.WIRED:
        return bool(hub.config.option_track_wired_clients)

    return not (
        hub.config.option_ignore_local_mac and is_locally_administered_mac(obj_id)
    )


@callback
def async_network_client_heartbeat_timedelta_fn(
    hub: UnifiHub, obj_id: str
) -> timedelta:
    """Return the detection time, never shorter than the polls allow."""
    return max(
        hub.config.option_detection_time,
        timedelta(seconds=NETWORK_MIN_DETECTION_TIME),
    )


@callback
def async_network_client_type_fn(api: aiounifi.Controller, obj_id: str) -> str | None:
    """Return the connection type of a client, None while it is not known."""
    client_type = api.network.clients[obj_id].type
    if client_type is NetworkClientType.UNKNOWN:
        return None
    return client_type.value


@callback
def async_device_heartbeat_timedelta_fn(hub: UnifiHub, obj_id: str) -> timedelta:
    """Check if device object is disabled."""
    device = hub.api.devices[obj_id]
    return timedelta(seconds=device.next_interval + 60)


@dataclass(frozen=True, kw_only=True)
class UnifiTrackerEntityDescription[HandlerT: UnifiApiHandler, ApiItemT: ApiItem](
    UnifiEntityDescription[HandlerT, ApiItemT], ScannerEntityDescription
):
    """Class describing UniFi device tracker entity."""

    heartbeat_timedelta_fn: Callable[[UnifiHub, str], timedelta]
    client_type_fn: Callable[[aiounifi.Controller, str], str | None] | None = None
    ip_address_fn: Callable[[aiounifi.Controller, str], str | None]
    is_connected_fn: Callable[[UnifiHub, str], bool]
    hostname_fn: Callable[[aiounifi.Controller, str], str | None]


ENTITY_DESCRIPTIONS: tuple[UnifiTrackerEntityDescription, ...] = (
    UnifiTrackerEntityDescription[Clients, Client](
        key="Client device scanner",
        allowed_fn=async_client_allowed_fn,
        entity_registry_enabled_default=False,
        api_handler_fn=lambda api: api.clients,
        device_info_fn=async_client_device_info_fn,
        event_is_on=set(WIRED_CONNECTION + WIRELESS_CONNECTION),
        event_to_subscribe=(
            WIRED_CONNECTION
            + WIRED_DISCONNECTION
            + WIRELESS_CONNECTION
            + WIRELESS_DISCONNECTION
        ),
        heartbeat_timedelta_fn=lambda hub, _: hub.config.option_detection_time,
        is_connected_fn=async_client_is_connected_fn,
        object_fn=lambda api, obj_id: api.clients[obj_id],
        unique_id_fn=lambda hub, obj_id: f"{hub.site}-{obj_id}",
        ip_address_fn=lambda api, obj_id: api.clients[obj_id].ip,
        hostname_fn=lambda api, obj_id: api.clients[obj_id].hostname,
    ),
    UnifiTrackerEntityDescription[Devices, Device](
        key="Device scanner",
        allowed_fn=lambda hub, obj_id: hub.config.option_track_devices,
        api_handler_fn=lambda api: api.devices,
        available_fn=async_device_available_fn,
        device_info_fn=async_device_device_info_fn,
        heartbeat_timedelta_fn=async_device_heartbeat_timedelta_fn,
        is_connected_fn=lambda hub, obj_id: hub.api.devices[obj_id].state == 1,
        object_fn=lambda api, obj_id: api.devices[obj_id],
        supported_fn=async_device_supported_fn,
        unique_id_fn=lambda hub, obj_id: obj_id,
        ip_address_fn=lambda api, obj_id: api.devices[obj_id].ip,
        hostname_fn=lambda api, obj_id: None,
    ),
)


NETWORK_API_ENTITY_DESCRIPTIONS: tuple[UnifiTrackerEntityDescription, ...] = (
    UnifiTrackerEntityDescription[NetworkClients, NetworkClient](
        key="Integration API client scanner",
        allowed_fn=async_network_client_allowed_fn,
        entity_registry_enabled_default=False,
        api_handler_fn=lambda api: api.network.clients,
        device_info_fn=async_network_client_device_info_fn,
        heartbeat_timedelta_fn=async_network_client_heartbeat_timedelta_fn,
        client_type_fn=async_network_client_type_fn,
        is_connected_fn=lambda hub, obj_id: hub.api.network.clients.is_connected(
            obj_id
        ),
        object_fn=lambda api, obj_id: api.network.clients[obj_id],
        unique_id_fn=lambda hub, obj_id: f"{hub.site}-{obj_id}",
        ip_address_fn=lambda api, obj_id: api.network.clients[obj_id].ip_address,
        hostname_fn=lambda api, obj_id: None,
    ),
    UnifiTrackerEntityDescription[NetworkDevices, NetworkDevice](
        key="Integration API device scanner",
        allowed_fn=lambda hub, obj_id: hub.config.option_track_devices,
        api_handler_fn=lambda api: api.network.devices,
        device_info_fn=async_network_device_device_info_fn,
        heartbeat_timedelta_fn=lambda hub, _: NETWORK_DEVICE_HEARTBEAT,
        is_connected_fn=lambda hub, obj_id: (
            hub.api.network.devices[obj_id].state is NetworkDeviceState.ONLINE
        ),
        object_fn=lambda api, obj_id: api.network.devices[obj_id],
        supported_fn=async_network_device_supported_fn,
        unique_id_fn=lambda hub, obj_id: obj_id,
        ip_address_fn=lambda api, obj_id: api.network.devices[obj_id].ip_address,
        hostname_fn=lambda api, obj_id: None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: UnifiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker for UniFi Network integration."""
    hub = config_entry.runtime_data
    hub.entity_loader.register_platform(
        async_add_entities,
        UnifiScannerEntity,
        NETWORK_API_ENTITY_DESCRIPTIONS
        if hub.config.api_key_only
        else ENTITY_DESCRIPTIONS,
    )


class UnifiScannerEntity[HandlerT: UnifiApiHandler, ApiItemT: ApiItem](
    UnifiEntity[HandlerT, ApiItemT], ScannerEntity
):
    """Representation of a UniFi scanner."""

    entity_description: UnifiTrackerEntityDescription

    _event_is_on: set[EventKey]
    _ignore_events: bool
    _is_connected: bool

    @callback
    @override
    def async_initiate_state(self) -> None:
        """Initiate entity state.

        Initiate is_connected.
        """
        description = self.entity_description
        # ScannerEntity disables trackers by default, which hides the description
        self._attr_entity_registry_enabled_default = (
            description.entity_registry_enabled_default
        )
        self._event_is_on = description.event_is_on or set()
        self._ignore_events = False
        self._is_connected = description.is_connected_fn(self.hub, self._obj_id)
        if self.is_connected:
            self.hub.update_heartbeat(
                self.unique_id,
                dt_util.utcnow()
                + description.heartbeat_timedelta_fn(self.hub, self._obj_id),
            )

    @property
    @override
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self._is_connected

    @property
    @override
    def hostname(self) -> str | None:
        """Return hostname of the device."""
        return self.entity_description.hostname_fn(self.api, self._obj_id)

    @property
    @override
    def ip_address(self) -> str | None:
        """Return the primary ip address of the device."""
        return self.entity_description.ip_address_fn(self.api, self._obj_id)

    @cached_property
    @override
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self._obj_id

    @cached_property
    @override
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._attr_unique_id

    @callback
    def _make_disconnected(self, *_: core_Event) -> None:
        """No heart beat by device."""
        self._is_connected = False
        self.async_write_ha_state()

    @callback
    @override
    def async_update_state(self, event: ItemEvent, obj_id: str) -> None:
        """Update entity state.

        Remove heartbeat check if hub connection state has changed
         and entity is unavailable.
        Update is_connected.
        Schedule new heartbeat check if connected.
        """
        description = self.entity_description
        hub = self.hub

        if event is ItemEvent.CHANGED:
            # Prioritize normal data updates over events
            self._ignore_events = True

        elif event is ItemEvent.ADDED and not self.available:
            # From unifi.entity.async_signal_reachable_callback
            # Controller connection state has changed and entity is unavailable
            # Cancel heartbeat
            hub.remove_heartbeat(self.unique_id)
            return

        obj_id = self._obj_id
        self._async_store_client_type()
        if is_connected := description.is_connected_fn(hub, obj_id):
            self._is_connected = is_connected
            self.hub.update_heartbeat(
                self.unique_id,
                dt_util.utcnow() + description.heartbeat_timedelta_fn(hub, obj_id),
            )

    @callback
    @override
    def async_event_callback(self, event: Event) -> None:
        """Event subscription callback."""
        obj_id = self._obj_id
        if event.mac != obj_id or self._ignore_events:
            return

        hub = self.hub
        if event.key in self._event_is_on:
            hub.remove_heartbeat(self.unique_id)
            self._is_connected = True
            self.async_write_ha_state()
            return

        hub.update_heartbeat(
            self.unique_id,
            dt_util.utcnow()
            + self.entity_description.heartbeat_timedelta_fn(hub, obj_id),
        )

    @callback
    def _async_store_client_type(self) -> None:
        """Remember the connection type so a restored client keeps its filters."""
        type_fn = self.entity_description.client_type_fn
        if (
            type_fn is None
            or self.registry_entry is None
            or (client_type := type_fn(self.api, self._obj_id)) is None
        ):
            return
        stored: Mapping[str, Any] = self.registry_entry.options.get(DOMAIN) or {}
        if stored.get(CLIENT_TYPE_OPTION) == client_type:
            return
        er.async_get(self.hass).async_update_entity_options(
            self.entity_id, DOMAIN, {CLIENT_TYPE_OPTION: client_type}
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        self._async_store_client_type()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{self.hub.signal_heartbeat_missed}_{self.unique_id}",
                self._make_disconnected,
            )
        )

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Disconnect object when removed."""
        await super().async_will_remove_from_hass()
        self.hub.remove_heartbeat(self.unique_id)

    @property
    @override
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the client state attributes."""
        if self.entity_description.key != "Client device scanner":
            return None

        client = self.entity_description.object_fn(self.api, self._obj_id)
        raw = client.raw

        attributes_to_check = CLIENT_STATIC_ATTRIBUTES
        if self.is_connected:
            attributes_to_check = CLIENT_CONNECTED_ALL_ATTRIBUTES

        return {k: raw[k] for k in attributes_to_check if k in raw}
