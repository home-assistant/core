"""Track both clients and devices using UniFi Network."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Generic, TypeVar

import aiounifi
from aiounifi.interfaces.api_handlers import ItemEvent
from aiounifi.interfaces.devices import Devices
from aiounifi.models.api import SOURCE_DATA, SOURCE_EVENT
from aiounifi.models.device import Device
from aiounifi.models.event import EventKey

from homeassistant.components.device_tracker import DOMAIN, ScannerEntity, SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from .const import DOMAIN as UNIFI_DOMAIN
from .controller import UniFiController
from .entity import UnifiEntity, UnifiEntityDescription
from .unifi_client import UniFiClientBase

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
    "hostname",
    "mac",
    "name",
    "oui",
]


CLIENT_CONNECTED_ALL_ATTRIBUTES = CLIENT_CONNECTED_ATTRIBUTES + CLIENT_STATIC_ATTRIBUTES

WIRED_CONNECTION = (EventKey.WIRED_CLIENT_CONNECTED,)
WIRELESS_CONNECTION = (
    EventKey.WIRELESS_CLIENT_CONNECTED,
    EventKey.WIRELESS_CLIENT_ROAM,
    EventKey.WIRELESS_CLIENT_ROAM_RADIO,
    EventKey.WIRELESS_GUEST_CONNECTED,
    EventKey.WIRELESS_GUEST_ROAM,
    EventKey.WIRELESS_GUEST_ROAM_RADIO,
)


_DataT = TypeVar("_DataT", bound=Device)
_HandlerT = TypeVar("_HandlerT", bound=Devices)


@callback
def async_device_available_fn(controller: UniFiController, obj_id: str) -> bool:
    """Check if device object is disabled."""
    device = controller.api.devices[obj_id]
    return controller.available and not device.disabled


@callback
def async_device_heartbeat_timedelta_fn(
    controller: UniFiController, obj_id: str
) -> timedelta:
    """Check if device object is disabled."""
    device = controller.api.devices[obj_id]
    return timedelta(seconds=device.next_interval + 60)


@dataclass
class UnifiEntityTrackerDescriptionMixin(Generic[_HandlerT, _DataT]):
    """Device tracker local functions."""

    heartbeat_timedelta_fn: Callable[[UniFiController, str], timedelta]
    ip_address_fn: Callable[[aiounifi.Controller, str], str]
    is_connected_fn: Callable[[UniFiController, str], bool]
    hostname_fn: Callable[[aiounifi.Controller, str], str | None]


@dataclass
class UnifiTrackerEntityDescription(
    UnifiEntityDescription[_HandlerT, _DataT],
    UnifiEntityTrackerDescriptionMixin[_HandlerT, _DataT],
):
    """Class describing UniFi device tracker entity."""


ENTITY_DESCRIPTIONS: tuple[UnifiTrackerEntityDescription, ...] = (
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

    controller.entities[DOMAIN] = {CLIENT_TRACKER: set(), DEVICE_TRACKER: set()}

    @callback
    def items_added(
        clients: set = controller.api.clients, devices: set = controller.api.devices
    ) -> None:
        """Update the values of the controller."""
        if controller.option_track_clients:
            add_client_entities(controller, async_add_entities, clients)

    for signal in (controller.signal_update, controller.signal_options_update):
        config_entry.async_on_unload(
            async_dispatcher_connect(hass, signal, items_added)
        )

    items_added()


@callback
def add_client_entities(controller, async_add_entities, clients):
    """Add new client tracker entities from the controller."""
    trackers = []

    for mac in clients:
        if mac in controller.entities[DOMAIN][UniFiClientTracker.TYPE] or not (
            client := controller.api.clients.get(mac)
        ):
            continue

        if mac not in controller.wireless_clients:
            if not controller.option_track_wired_clients:
                continue
        elif (
            client.essid
            and controller.option_ssid_filter
            and client.essid not in controller.option_ssid_filter
        ):
            continue

        trackers.append(UniFiClientTracker(client, controller))

    async_add_entities(trackers)


class UniFiClientTracker(UniFiClientBase, ScannerEntity):
    """Representation of a network client."""

    DOMAIN = DOMAIN
    TYPE = CLIENT_TRACKER

    def __init__(self, client, controller):
        """Set up tracked client."""
        super().__init__(client, controller)

        self._controller_connection_state_changed = False

        self._only_listen_to_data_source = False

        last_seen = client.last_seen or 0
        self.schedule_update = self._is_connected = (
            self.is_wired == client.is_wired
            and dt_util.utcnow() - dt_util.utc_from_timestamp(float(last_seen))
            < controller.option_detection_time
        )

    @callback
    def _async_log_debug_data(self, method: str) -> None:
        """Print debug data about entity."""
        if not LOGGER.isEnabledFor(logging.DEBUG):
            return
        last_seen = self.client.last_seen or 0
        LOGGER.debug(
            "%s [%s, %s] [%s %s] [%s] %s (%s)",
            method,
            self.entity_id,
            self.client.mac,
            self.schedule_update,
            self._is_connected,
            dt_util.utc_from_timestamp(float(last_seen)),
            dt_util.utcnow() - dt_util.utc_from_timestamp(float(last_seen)),
            last_seen,
        )

    async def async_added_to_hass(self) -> None:
        """Watch object when added."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{self.controller.signal_heartbeat_missed}_{self.unique_id}",
                self._make_disconnected,
            )
        )
        await super().async_added_to_hass()
        self._async_log_debug_data("added_to_hass")

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect object when removed."""
        self.controller.async_heartbeat(self.unique_id)
        await super().async_will_remove_from_hass()

    @callback
    def async_signal_reachable_callback(self) -> None:
        """Call when controller connection state change."""
        self._controller_connection_state_changed = True
        super().async_signal_reachable_callback()

    @callback
    def async_update_callback(self) -> None:
        """Update the clients state."""

        if self._controller_connection_state_changed:
            self._controller_connection_state_changed = False

            if self.controller.available:
                self.schedule_update = True

            else:
                self.controller.async_heartbeat(self.unique_id)
                super().async_update_callback()

        elif (
            self.client.last_updated == SOURCE_DATA
            and self.is_wired == self.client.is_wired
        ):
            self._is_connected = True
            self.schedule_update = True
            self._only_listen_to_data_source = True

        elif (
            self.client.last_updated == SOURCE_EVENT
            and not self._only_listen_to_data_source
        ):
            if (self.is_wired and self.client.event.key in WIRED_CONNECTION) or (
                not self.is_wired and self.client.event.key in WIRELESS_CONNECTION
            ):
                self._is_connected = True
                self.schedule_update = False
                self.controller.async_heartbeat(self.unique_id)
                super().async_update_callback()

            else:
                self.schedule_update = True

        self._async_log_debug_data("update_callback")

        if self.schedule_update:
            self.schedule_update = False
            self.controller.async_heartbeat(
                self.unique_id, dt_util.utcnow() + self.controller.option_detection_time
            )

            super().async_update_callback()

    @callback
    def _make_disconnected(self, *_):
        """No heart beat by device."""
        self._is_connected = False
        self.async_write_ha_state()
        self._async_log_debug_data("make_disconnected")

    @property
    def is_connected(self):
        """Return true if the client is connected to the network."""
        if (
            not self.is_wired
            and self.client.essid
            and self.controller.option_ssid_filter
            and self.client.essid not in self.controller.option_ssid_filter
        ):
            return False

        return self._is_connected

    @property
    def source_type(self) -> SourceType:
        """Return the source type of the client."""
        return SourceType.ROUTER

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this client."""
        return f"{self.client.mac}-{self.controller.site}"

    @property
    def extra_state_attributes(self):
        """Return the client state attributes."""
        raw = self.client.raw

        attributes_to_check = CLIENT_STATIC_ATTRIBUTES
        if self.is_connected:
            attributes_to_check = CLIENT_CONNECTED_ALL_ATTRIBUTES

        attributes = {k: raw[k] for k in attributes_to_check if k in raw}
        attributes["is_wired"] = self.is_wired

        return attributes

    @property
    def ip_address(self) -> str:
        """Return the primary ip address of the device."""
        return self.client.raw.get("ip")

    @property
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self.client.raw.get("mac")

    @property
    def hostname(self) -> str:
        """Return hostname of the device."""
        return self.client.raw.get("hostname")

    async def options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        if not self.controller.option_track_clients:
            await self.remove_item({self.client.mac})

        elif self.is_wired:
            if not self.controller.option_track_wired_clients:
                await self.remove_item({self.client.mac})

        elif (
            self.controller.option_ssid_filter
            and self.client.essid not in self.controller.option_ssid_filter
        ):
            await self.remove_item({self.client.mac})


class UnifiScannerEntity(UnifiEntity[_HandlerT, _DataT], ScannerEntity):
    """Representation of a UniFi scanner."""

    entity_description: UnifiTrackerEntityDescription

    _ignore_events: bool
    _is_connected: bool

    @callback
    def async_initiate_state(self) -> None:
        """Initiate entity state.

        Initiate is_connected.
        """
        description = self.entity_description
        self._ignore_events = False
        self._is_connected = description.is_connected_fn(self.controller, self._obj_id)

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
    def _make_disconnected(self, *_) -> None:
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

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{self.controller.signal_heartbeat_missed}_{self._obj_id}",
                self._make_disconnected,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect object when removed."""
        await super().async_will_remove_from_hass()
        self.controller.async_heartbeat(self.unique_id)
