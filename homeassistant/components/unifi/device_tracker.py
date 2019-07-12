"""Support for Unifi WAP controllers."""
from datetime import timedelta

import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import unifi
from homeassistant.components.device_tracker import PLATFORM_SCHEMA
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import SOURCE_TYPE_ROUTER
from homeassistant.core import callback
from homeassistant.const import (
    CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_PORT, CONF_VERIFY_SSL)
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

from .const import (
    CONF_CONTROLLER, CONF_DETECTION_TIME, CONF_SITE_ID, CONF_SSID_FILTER,
    CONTROLLER_ID, DOMAIN as UNIFI_DOMAIN)

LOGGER = logging.getLogger(__name__)

DEVICE_ATTRIBUTES = [
    '_is_guest_by_uap', 'ap_mac', 'authorized', 'bssid', 'ccq',
    'channel', 'essid', 'hostname', 'ip', 'is_11r', 'is_guest', 'is_wired',
    'mac', 'name', 'noise', 'noted', 'oui', 'qos_policy_applied', 'radio',
    'radio_proto', 'rssi', 'signal', 'site_id', 'vlan'
]

CONF_DT_SITE_ID = 'site_id'

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 8443
DEFAULT_VERIFY_SSL = True
DEFAULT_DETECTION_TIME = timedelta(seconds=300)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_DT_SITE_ID, default='default'): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): vol.Any(
        cv.boolean, cv.isfile)
}, extra=vol.ALLOW_EXTRA)


async def async_setup_scanner(hass, config, sync_see, discovery_info):
    """Set up the Unifi integration."""
    config[CONF_SITE_ID] = config.pop(CONF_DT_SITE_ID)  # Current from legacy

    exist = False

    for entry in hass.config_entries.async_entries(UNIFI_DOMAIN):
        if config[CONF_HOST] == entry.data[CONF_CONTROLLER][CONF_HOST] and \
                config[CONF_SITE_ID] == \
                entry.data[CONF_CONTROLLER][CONF_SITE_ID]:
            exist = True
            break

    if not exist:
        hass.async_create_task(hass.config_entries.flow.async_init(
            UNIFI_DOMAIN, context={'source': config_entries.SOURCE_IMPORT},
            data=config
        ))

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
                CONF_SSID_FILTER in controller.unifi_config and \
                client.essid not in controller.unifi_config[CONF_SSID_FILTER]:
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
        detection_time = self.controller.unifi_config.get(
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

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attributes = {}

        for variable in DEVICE_ATTRIBUTES:
            if variable in self.client.raw:
                attributes[variable] = self.client.raw[variable]

        return attributes
