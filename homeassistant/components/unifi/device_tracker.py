"""Track both clients and devices using UniFi Network."""

from datetime import timedelta
import logging

from aiounifi.api import SOURCE_DATA, SOURCE_EVENT
from aiounifi.events import (
    ACCESS_POINT_UPGRADED,
    GATEWAY_UPGRADED,
    SWITCH_UPGRADED,
    WIRED_CLIENT_CONNECTED,
    WIRELESS_CLIENT_CONNECTED,
    WIRELESS_CLIENT_ROAM,
    WIRELESS_CLIENT_ROAMRADIO,
    WIRELESS_GUEST_CONNECTED,
    WIRELESS_GUEST_ROAM,
    WIRELESS_GUEST_ROAMRADIO,
)

from homeassistant.components.device_tracker import DOMAIN
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from .const import DOMAIN as UNIFI_DOMAIN
from .controller import UniFiController
from .unifi_client import UniFiClientBase
from .unifi_entity_base import UniFiBase

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

DEVICE_UPGRADED = (ACCESS_POINT_UPGRADED, GATEWAY_UPGRADED, SWITCH_UPGRADED)

WIRED_CONNECTION = (WIRED_CLIENT_CONNECTED,)
WIRELESS_CONNECTION = (
    WIRELESS_CLIENT_CONNECTED,
    WIRELESS_CLIENT_ROAM,
    WIRELESS_CLIENT_ROAMRADIO,
    WIRELESS_GUEST_CONNECTED,
    WIRELESS_GUEST_ROAM,
    WIRELESS_GUEST_ROAMRADIO,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up device tracker for UniFi Network integration."""
    controller: UniFiController = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
    controller.entities[DOMAIN] = {CLIENT_TRACKER: set(), DEVICE_TRACKER: set()}

    @callback
    def items_added(
        clients: set = controller.api.clients, devices: set = controller.api.devices
    ) -> None:
        """Update the values of the controller."""
        if controller.option_track_clients:
            add_client_entities(controller, async_add_entities, clients)

        if controller.option_track_devices:
            add_device_entities(controller, async_add_entities, devices)

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

    if trackers:
        async_add_entities(trackers)


@callback
def add_device_entities(controller, async_add_entities, devices):
    """Add new device tracker entities from the controller."""
    trackers = []

    for mac in devices:
        if mac in controller.entities[DOMAIN][UniFiDeviceTracker.TYPE]:
            continue

        device = controller.api.devices[mac]
        trackers.append(UniFiDeviceTracker(device, controller))

    if trackers:
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

            if (self.is_wired and self.client.event.event in WIRED_CONNECTION) or (
                not self.is_wired and self.client.event.event in WIRELESS_CONNECTION
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


class UniFiDeviceTracker(UniFiBase, ScannerEntity):
    """Representation of a network infrastructure device."""

    DOMAIN = DOMAIN
    TYPE = DEVICE_TRACKER

    def __init__(self, device, controller):
        """Set up tracked device."""
        super().__init__(device, controller)

        self.device = self._item
        self._is_connected = device.state == 1
        self._controller_connection_state_changed = False
        self.schedule_update = False

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
        """Update the devices' state."""

        if self._controller_connection_state_changed:
            self._controller_connection_state_changed = False

            if self.controller.available:
                if self._is_connected:
                    self.schedule_update = True

            else:
                self.controller.async_heartbeat(self.unique_id)

        elif self.device.last_updated == SOURCE_DATA:
            self._is_connected = True
            self.schedule_update = True

        if self.schedule_update:
            self.schedule_update = False
            self.controller.async_heartbeat(
                self.unique_id,
                dt_util.utcnow() + timedelta(seconds=self.device.next_interval + 60),
            )

        super().async_update_callback()

    @callback
    def _make_disconnected(self, *_):
        """No heart beat by device."""
        self._is_connected = False
        self.async_write_ha_state()

    @property
    def is_connected(self):
        """Return true if the device is connected to the network."""
        return self._is_connected

    @property
    def source_type(self) -> SourceType:
        """Return the source type of the device."""
        return SourceType.ROUTER

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self.device.name or self.device.model

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this device."""
        return self.device.mac

    @property
    def available(self) -> bool:
        """Return if controller is available."""
        return not self.device.disabled and self.controller.available

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        if self.device.state == 0:
            return {}

        attributes = {}

        if self.device.has_fan:
            attributes["fan_level"] = self.device.fan_level

        if self.device.overheating:
            attributes["overheating"] = self.device.overheating

        if self.device.upgradable:
            attributes["upgradable"] = self.device.upgradable

        return attributes

    @property
    def ip_address(self) -> str:
        """Return the primary ip address of the device."""
        return self.device.ip

    @property
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self.device.mac

    async def options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        if not self.controller.option_track_devices:
            await self.remove_item({self.device.mac})
