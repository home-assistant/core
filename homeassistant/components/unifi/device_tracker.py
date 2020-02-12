"""Track devices using UniFi controllers."""
import logging

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import SOURCE_TYPE_ROUTER
from homeassistant.components.unifi.config_flow import get_controller_from_config_entry
from homeassistant.core import callback
from homeassistant.helpers import entity_registry
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_registry import DISABLED_CONFIG_ENTRY
import homeassistant.util.dt as dt_util

from .const import ATTR_MANUFACTURER
from .unifi_client import UniFiClient

LOGGER = logging.getLogger(__name__)

DEVICE_ATTRIBUTES = [
    "_is_guest_by_uap",
    "ap_mac",
    "authorized",
    "essid",
    "hostname",
    "ip",
    "is_11r",
    "is_guest",
    "mac",
    "name",
    "noted",
    "oui",
    "qos_policy_applied",
    "radio",
    "radio_proto",
    "site_id",
    "vlan",
]


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up device tracker for UniFi component."""
    controller = get_controller_from_config_entry(hass, config_entry)
    tracked = {}

    registry = await entity_registry.async_get_registry(hass)

    # Restore clients that is not a part of active clients list.
    for entity in registry.entities.values():

        if (
            entity.config_entry_id == config_entry.entry_id
            and entity.domain == DEVICE_TRACKER_DOMAIN
            and "-" in entity.unique_id
        ):

            mac, _ = entity.unique_id.split("-", 1)

            if mac in controller.api.clients or mac not in controller.api.clients_all:
                continue

            client = controller.api.clients_all[mac]
            controller.api.clients.process_raw([client.raw])

    @callback
    def update_controller():
        """Update the values of the controller."""
        add_entities(controller, async_add_entities, tracked)

    controller.listeners.append(
        async_dispatcher_connect(hass, controller.signal_update, update_controller)
    )

    @callback
    def update_disable_on_entities():
        """Update the values of the controller."""
        for entity in tracked.values():

            if entity.entity_registry_enabled_default == entity.enabled:
                continue

            disabled_by = None
            if not entity.entity_registry_enabled_default and entity.enabled:
                disabled_by = DISABLED_CONFIG_ENTRY

            registry.async_update_entity(
                entity.registry_entry.entity_id, disabled_by=disabled_by
            )

    controller.listeners.append(
        async_dispatcher_connect(
            hass, controller.signal_options_update, update_disable_on_entities
        )
    )

    update_controller()


@callback
def add_entities(controller, async_add_entities, tracked):
    """Add new tracker entities from the controller."""
    new_tracked = []

    for items, tracker_class in (
        (controller.api.clients, UniFiClientTracker),
        (controller.api.devices, UniFiDeviceTracker),
    ):

        for item_id in items:

            if item_id in tracked:
                continue

            tracked[item_id] = tracker_class(items[item_id], controller)
            new_tracked.append(tracked[item_id])

    if new_tracked:
        async_add_entities(new_tracked)


class UniFiClientTracker(UniFiClient, ScannerEntity):
    """Representation of a network client."""

    def __init__(self, client, controller):
        """Set up tracked client."""
        super().__init__(client, controller)

        self.wired_bug = None
        if self.is_wired != self.client.is_wired:
            self.wired_bug = dt_util.utcnow() - self.controller.option_detection_time

    @property
    def entity_registry_enabled_default(self):
        """Return if the entity should be enabled when first added to the entity registry."""
        if not self.controller.option_track_clients:
            return False

        if (
            not self.is_wired
            and self.controller.option_ssid_filter
            and self.client.essid not in self.controller.option_ssid_filter
        ):
            return False

        if not self.controller.option_track_wired_clients and self.is_wired:
            return False

        return True

    @property
    def is_connected(self):
        """Return true if the client is connected to the network.

        If is_wired and client.is_wired differ it means that the device is offline and UniFi bug shows device as wired.
        """
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

        for variable in DEVICE_ATTRIBUTES:
            if variable in self.client.raw:
                attributes[variable] = self.client.raw[variable]

        attributes["is_wired"] = self.is_wired

        return attributes


class UniFiDeviceTracker(ScannerEntity):
    """Representation of a network infrastructure device."""

    def __init__(self, device, controller):
        """Set up tracked device."""
        self.device = device
        self.controller = controller
        self.listeners = []

    @property
    def entity_registry_enabled_default(self):
        """Return if the entity should be enabled when first added to the entity registry."""
        if self.controller.option_track_devices:
            return True
        return False

    async def async_added_to_hass(self):
        """Subscribe to device events."""
        LOGGER.debug("New UniFi device tracker %s (%s)", self.name, self.device.mac)
        self.device.register_callback(self.async_update_callback)
        self.listeners.append(
            async_dispatcher_connect(
                self.hass, self.controller.signal_reachable, self.async_update_callback
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect device object when removed."""
        self.device.remove_callback(self.async_update_callback)
        for unsub_dispatcher in self.listeners:
            unsub_dispatcher()

    @callback
    def async_update_callback(self):
        """Update the sensor's state."""
        LOGGER.debug("Updating UniFi tracked device %s", self.entity_id)

        self.async_schedule_update_ha_state()

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

    @property
    def should_poll(self):
        """No polling needed."""
        return False
