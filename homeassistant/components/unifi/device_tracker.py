"""Track both clients and devices using UniFi Network."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any, Generic

import aiounifi
from aiounifi.interfaces.api_handlers import ItemEvent
from aiounifi.interfaces.clients import Clients
from aiounifi.interfaces.devices import Devices
from aiounifi.models.api import ApiItemT
from aiounifi.models.client import Client
from aiounifi.models.device import Device
from aiounifi.models.event import Event, EventKey

from homeassistant.components.device_tracker import ScannerEntity, SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event as core_Event, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from .const import DOMAIN as UNIFI_DOMAIN
from .controller import UniFiController
from .entity import (
    HandlerT,
    UnifiEntity,
    UnifiEntityDescription,
    async_device_available_fn,
)

LOGGER = logging.getLogger(__name__)

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
def async_client_allowed_fn(controller: UniFiController, obj_id: str) -> bool:
    """Check if client is allowed."""
    if not controller.option_track_clients:
        return False

    client = controller.api.clients[obj_id]
    if client.mac not in controller.wireless_clients:
        if not controller.option_track_wired_clients:
            return False

    elif (
        client.essid
        and controller.option_ssid_filter
        and client.essid not in controller.option_ssid_filter
    ):
        return False

    return True


@callback
def async_client_is_connected_fn(controller: UniFiController, obj_id: str) -> bool:
    """Check if device object is disabled."""
    client = controller.api.clients[obj_id]

    if controller.wireless_clients.is_wireless(client) and client.is_wired:
        if not controller.option_ignore_wired_bug:
            return False  # Wired bug in action

    if (
        not client.is_wired
        and client.essid
        and controller.option_ssid_filter
        and client.essid not in controller.option_ssid_filter
    ):
        return False

    if (
        dt_util.utcnow() - dt_util.utc_from_timestamp(client.last_seen or 0)
        > controller.option_detection_time
    ):
        return False

    return True


@callback
def async_device_heartbeat_timedelta_fn(
    controller: UniFiController, obj_id: str
) -> timedelta:
    """Check if device object is disabled."""
    device = controller.api.devices[obj_id]
    return timedelta(seconds=device.next_interval + 60)


@dataclass
class UnifiEntityTrackerDescriptionMixin(Generic[HandlerT, ApiItemT]):
    """Device tracker local functions."""

    heartbeat_timedelta_fn: Callable[[UniFiController, str], timedelta]
    ip_address_fn: Callable[[aiounifi.Controller, str], str]
    is_connected_fn: Callable[[UniFiController, str], bool]
    hostname_fn: Callable[[aiounifi.Controller, str], str | None]


@dataclass
class UnifiTrackerEntityDescription(
    UnifiEntityDescription[HandlerT, ApiItemT],
    UnifiEntityTrackerDescriptionMixin[HandlerT, ApiItemT],
):
    """Class describing UniFi device tracker entity."""


ENTITY_DESCRIPTIONS: tuple[UnifiTrackerEntityDescription, ...] = (
    UnifiTrackerEntityDescription[Clients, Client](
        key="Client device scanner",
        has_entity_name=True,
        allowed_fn=async_client_allowed_fn,
        api_handler_fn=lambda api: api.clients,
        available_fn=lambda controller, obj_id: controller.available,
        device_info_fn=lambda api, obj_id: None,
        event_is_on=(WIRED_CONNECTION + WIRELESS_CONNECTION),
        event_to_subscribe=(
            WIRED_CONNECTION
            + WIRED_DISCONNECTION
            + WIRELESS_CONNECTION
            + WIRELESS_DISCONNECTION
        ),
        heartbeat_timedelta_fn=lambda controller, _: controller.option_detection_time,
        is_connected_fn=async_client_is_connected_fn,
        name_fn=lambda client: client.name or client.hostname,
        object_fn=lambda api, obj_id: api.clients[obj_id],
        should_poll=False,
        supported_fn=lambda controller, obj_id: True,
        unique_id_fn=lambda controller, obj_id: f"{obj_id}-{controller.site}",
        ip_address_fn=lambda api, obj_id: api.clients[obj_id].ip,
        hostname_fn=lambda api, obj_id: api.clients[obj_id].hostname,
    ),
    UnifiTrackerEntityDescription[Devices, Device](
        key="Device scanner",
        has_entity_name=True,
        icon="mdi:ethernet",
        allowed_fn=lambda controller, obj_id: controller.option_track_devices,
        api_handler_fn=lambda api: api.devices,
        available_fn=async_device_available_fn,
        device_info_fn=lambda api, obj_id: None,
        event_is_on=None,
        event_to_subscribe=None,
        heartbeat_timedelta_fn=async_device_heartbeat_timedelta_fn,
        is_connected_fn=lambda ctrlr, obj_id: ctrlr.api.devices[obj_id].state == 1,
        name_fn=lambda device: device.name or device.model,
        object_fn=lambda api, obj_id: api.devices[obj_id],
        should_poll=False,
        supported_fn=lambda controller, obj_id: True,
        unique_id_fn=lambda controller, obj_id: obj_id,
        ip_address_fn=lambda api, obj_id: api.devices[obj_id].ip,
        hostname_fn=lambda api, obj_id: None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up device tracker for UniFi Network integration."""
    controller: UniFiController = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
    controller.register_platform_add_entities(
        UnifiScannerEntity, ENTITY_DESCRIPTIONS, async_add_entities
    )


class UnifiScannerEntity(UnifiEntity[HandlerT, ApiItemT], ScannerEntity):
    """Representation of a UniFi scanner."""

    entity_description: UnifiTrackerEntityDescription

    _event_is_on: tuple[EventKey, ...]
    _ignore_events: bool
    _is_connected: bool

    @callback
    def async_initiate_state(self) -> None:
        """Initiate entity state.

        Initiate is_connected.
        """
        description = self.entity_description
        self._event_is_on = description.event_is_on or ()
        self._ignore_events = False
        self._is_connected = description.is_connected_fn(self.controller, self._obj_id)
        if self.is_connected:
            self.controller.async_heartbeat(
                self.unique_id,
                dt_util.utcnow()
                + description.heartbeat_timedelta_fn(self.controller, self._obj_id),
            )

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self._is_connected

    @property
    def hostname(self) -> str | None:
        """Return hostname of the device."""
        return self.entity_description.hostname_fn(self.controller.api, self._obj_id)

    @property
    def ip_address(self) -> str:
        """Return the primary ip address of the device."""
        return self.entity_description.ip_address_fn(self.controller.api, self._obj_id)

    @property
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self._obj_id

    @property
    def source_type(self) -> SourceType:
        """Return the source type, eg gps or router, of the device."""
        return SourceType.ROUTER

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._attr_unique_id

    @callback
    def _make_disconnected(self, *_: core_Event) -> None:
        """No heart beat by device."""
        self._is_connected = False
        self.async_write_ha_state()

    @callback
    def async_update_state(self, event: ItemEvent, obj_id: str) -> None:
        """Update entity state.

        Remove heartbeat check if controller state has changed
         and entity is unavailable.
        Update is_connected.
        Schedule new heartbeat check if connected.
        """
        description = self.entity_description

        if event == ItemEvent.CHANGED:
            # Prioritize normal data updates over events
            self._ignore_events = True

        elif event == ItemEvent.ADDED and not self.available:
            # From unifi.entity.async_signal_reachable_callback
            # Controller connection state has changed and entity is unavailable
            # Cancel heartbeat
            self.controller.async_heartbeat(self.unique_id)
            return

        if is_connected := description.is_connected_fn(self.controller, self._obj_id):
            self._is_connected = is_connected
            self.controller.async_heartbeat(
                self.unique_id,
                dt_util.utcnow()
                + description.heartbeat_timedelta_fn(self.controller, self._obj_id),
            )

    @callback
    def async_event_callback(self, event: Event) -> None:
        """Event subscription callback."""
        if event.mac != self._obj_id or self._ignore_events:
            return

        if event.key in self._event_is_on:
            self.controller.async_heartbeat(self.unique_id)
            self._is_connected = True
            self.async_write_ha_state()
            return

        self.controller.async_heartbeat(
            self.unique_id,
            dt_util.utcnow()
            + self.entity_description.heartbeat_timedelta_fn(
                self.controller, self._obj_id
            ),
        )

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{self.controller.signal_heartbeat_missed}_{self.unique_id}",
                self._make_disconnected,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect object when removed."""
        await super().async_will_remove_from_hass()
        self.controller.async_heartbeat(self.unique_id)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the client state attributes."""
        if self.entity_description.key != "Client device scanner":
            return None

        client = self.entity_description.object_fn(self.controller.api, self._obj_id)
        raw = client.raw

        attributes_to_check = CLIENT_STATIC_ATTRIBUTES
        if self.is_connected:
            attributes_to_check = CLIENT_CONNECTED_ALL_ATTRIBUTES

        attributes = {k: raw[k] for k in attributes_to_check if k in raw}

        return attributes
