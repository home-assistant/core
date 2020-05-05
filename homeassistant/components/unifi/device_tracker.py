"""Track devices using UniFi controllers."""
import logging

from homeassistant.components.device_tracker import DOMAIN
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import SOURCE_TYPE_ROUTER
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_point_in_utc_time
import homeassistant.util.dt as dt_util

from .const import ATTR_MANUFACTURER, DOMAIN as UNIFI_DOMAIN
from .unifi_client import UniFiClient
from .unifi_entity_base import UniFiBase

LOGGER = logging.getLogger(__name__)

CLIENT_CONNECTED_ATTRIBUTES = [
    "_is_guest_by_uap",
    "ap_mac",
    "authorized",
    "essid",
    "ip",
    "is_11r",
    "is_guest",
    "noted",
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

CLIENT_TRACKER = "client"
DEVICE_TRACKER = "device"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up device tracker for UniFi component."""
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
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
        controller.listeners.append(async_dispatcher_connect(hass, signal, items_added))

    items_added()


@callback
def add_client_entities(controller, async_add_entities, clients):
    """Add new client tracker entities from the controller."""
    trackers = []

    for mac in clients:
        if mac in controller.entities[DOMAIN][UniFiClientTracker.TYPE]:
            continue

        client = controller.api.clients[mac]

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


class UniFiClientTracker(UniFiClient, ScannerEntity):
    """Representation of a network client."""

    DOMAIN = DOMAIN
    TYPE = CLIENT_TRACKER

    def __init__(self, client, controller):
        """Set up tracked client."""
        super().__init__(client, controller)

        self.cancel_scheduled_update = None
        self.is_disconnected = None
        self.wired_bug = None
        if self.is_wired != self.client.is_wired:
            self.wired_bug = dt_util.utcnow() - self.controller.option_detection_time

    @property
    def is_connected(self):
        """Return true if the client is connected to the network.

        If connected to unwanted ssid return False.
        If is_wired and client.is_wired differ it means that the device is offline and UniFi bug shows device as wired.
        """

        @callback
        def _scheduled_update(now):
            """Scheduled callback for update."""
            self.is_disconnected = True
            self.cancel_scheduled_update = None
            self.async_write_ha_state()

        if (self.is_wired and self.wired_connection) or (
            not self.is_wired and self.wireless_connection
        ):
            if self.cancel_scheduled_update:
                self.cancel_scheduled_update()
                self.cancel_scheduled_update = None

            self.is_disconnected = False

        if (self.is_wired and self.wired_connection is False) or (
            not self.is_wired and self.wireless_connection is False
        ):
            if not self.is_disconnected and not self.cancel_scheduled_update:
                self.cancel_scheduled_update = async_track_point_in_utc_time(
                    self.hass,
                    _scheduled_update,
                    dt_util.utcnow() + self.controller.option_detection_time,
                )

        # SSID filter
        if (
            not self.is_wired
            and self.client.essid
            and self.controller.option_ssid_filter
            and self.client.essid not in self.controller.option_ssid_filter
            and not self.cancel_scheduled_update
        ):
            return False

        # A client that has never been seen cannot be connected.
        if self.client.last_seen is None:
            return False

        if self.is_disconnected is not None:
            return not self.is_disconnected

        if self.is_wired != self.client.is_wired:
            if not self.wired_bug:
                self.wired_bug = dt_util.utcnow()
            since_last_seen = dt_util.utcnow() - self.wired_bug

        else:
            self.wired_bug = None

            since_last_seen = dt_util.utcnow() - dt_util.utc_from_timestamp(
                float(self.client.last_seen)
            )

        if since_last_seen < self.controller.option_detection_time:
            return True

        return False

    @property
    def source_type(self):
        """Return the source type of the client."""
        return SOURCE_TYPE_ROUTER

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this client."""
        return f"{self.client.mac}-{self.controller.site}"

    @property
    def device_state_attributes(self):
        """Return the client state attributes."""
        attributes = {}

        attributes["is_wired"] = self.is_wired

        for variable in CLIENT_STATIC_ATTRIBUTES + CLIENT_CONNECTED_ATTRIBUTES:
            if variable in self.client.raw:
                if self.is_disconnected and variable in CLIENT_CONNECTED_ATTRIBUTES:
                    continue
                attributes[variable] = self.client.raw[variable]

        return attributes

    async def options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        if not self.controller.option_track_clients:
            await self.async_remove()

        elif self.is_wired:
            if not self.controller.option_track_wired_clients:
                await self.async_remove()
        else:
            if (
                self.controller.option_ssid_filter
                and self.client.essid not in self.controller.option_ssid_filter
            ):
                await self.async_remove()


class UniFiDeviceTracker(UniFiBase, ScannerEntity):
    """Representation of a network infrastructure device."""

    DOMAIN = DOMAIN
    TYPE = DEVICE_TRACKER

    def __init__(self, device, controller):
        """Set up tracked device."""
        self.device = device
        super().__init__(controller)

    @property
    def mac(self):
        """Return MAC of device."""
        return self.device.mac

    async def async_added_to_hass(self):
        """Subscribe to device events."""
        await super().async_added_to_hass()
        self.device.register_callback(self.async_update_callback)

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect device object when removed."""
        await super().async_will_remove_from_hass()
        self.device.remove_callback(self.async_update_callback)

    @callback
    def async_update_callback(self):
        """Update the sensor's state."""
        LOGGER.debug("Updating device %s (%s)", self.entity_id, self.device.mac)
        self.async_write_ha_state()

    @property
    def is_connected(self):
        """Return true if the device is connected to the network."""
        if self.device.state == 1 and (
            dt_util.utcnow() - dt_util.utc_from_timestamp(float(self.device.last_seen))
            < self.controller.option_detection_time
        ):
            return True

        return False

    @property
    def source_type(self):
        """Return the source type of the device."""
        return SOURCE_TYPE_ROUTER

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
    def device_info(self):
        """Return a device description for device registry."""
        info = {
            "connections": {(CONNECTION_NETWORK_MAC, self.device.mac)},
            "manufacturer": ATTR_MANUFACTURER,
            "model": self.device.model,
            "sw_version": self.device.version,
        }

        if self.device.name:
            info["name"] = self.device.name

        return info

    @property
    def device_state_attributes(self):
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

    async def options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        if not self.controller.option_track_devices:
            await self.async_remove()
