"""Support for Unifi WAP controllers."""
from datetime import timedelta
import logging

from homeassistant.components import unifi
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import SOURCE_TYPE_ROUTER
from homeassistant.core import callback
from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect

import homeassistant.util.dt as dt_util

from .const import (
    CONF_CONTROLLER, CONF_DETECTION_TIME, CONF_SITE_ID, CONF_SSID_FILTER,
    CONTROLLER_ID, UNIFI_CONFIG)

LOGGER = logging.getLogger(__name__)

DEFAULT_DETECTION_TIME = timedelta(seconds=300)


async def async_setup_scanner(hass, config, sync_see, discovery_info):
    """Set up the Unifi integration."""
    return True


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up device tracker for UniFi component."""
    controller_id = CONTROLLER_ID.format(
        host=config_entry.data[CONF_CONTROLLER][CONF_HOST],
        site=config_entry.data[CONF_CONTROLLER][CONF_SITE_ID],
    )
    controller = hass.data[unifi.DOMAIN][controller_id]
    tracked = {}

    @callback
    def update_controller():
        """Update the values of the controller."""
        update_items(controller, async_add_entities, tracked)

    async_dispatcher_connect(hass, controller.event_update, update_controller)

    update_controller()


@callback
def update_items(controller, async_add_entities, tracked):
    """Update tracked device state from the controller."""
    new_tracked = []

    for client_id in controller.api.clients:

        if client_id in tracked:
            LOGGER.debug("Updating UniFi tracked device %s (%s)",
                         tracked[client_id].entity_id,
                         tracked[client_id].client.mac)
            tracked[client_id].async_schedule_update_ha_state()
            continue

        client = controller.api.clients[client_id]

        if not client.is_wired and \
                CONF_SSID_FILTER in controller.hass.data[UNIFI_CONFIG] and \
                client.essid not in \
                controller.hass.data[UNIFI_CONFIG][CONF_SSID_FILTER]:
            continue

        tracked[client_id] = UniFiClientTracker(client, controller)
        new_tracked.append(tracked[client_id])
        LOGGER.debug("New UniFi switch %s (%s)", client.hostname, client.mac)

    if new_tracked:
        async_add_entities(new_tracked)


class UniFiClientTracker(ScannerEntity):
    """Representation of a network device."""

    def __init__(self, client, controller):
        """Set up tracked device."""
        self.client = client
        self.controller = controller

    async def async_update(self):
        """Synchronize state with controller."""
        await self.controller.request_update()

    @property
    def is_connected(self):
        """Return true if the device is connected to the network."""
        detection_time = self.controller.hass.data[UNIFI_CONFIG].get(
            CONF_DETECTION_TIME, DEFAULT_DETECTION_TIME)

        if (dt_util.utcnow() - dt_util.utc_from_timestamp(float(
                self.client.last_seen))) < detection_time:
            return True
        return False

    @property
    def source_type(self):
        """Return the source type of the device."""
        return SOURCE_TYPE_ROUTER

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self.client.name or self.client.hostname

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this client."""
        return '{}-{}'.format(self.client.mac, self.controller.site)

    @property
    def available(self) -> bool:
        """Return if controller is available."""
        return self.controller.available

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return {
            'connections': {(CONNECTION_NETWORK_MAC, self.client.mac)}
        }
