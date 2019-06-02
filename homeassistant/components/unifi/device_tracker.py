"""Support for Unifi WAP controllers."""
import asyncio
import logging
from datetime import timedelta
import voluptuous as vol

import async_timeout
import aiounifi

from homeassistant import config_entries
from homeassistant.components import unifi
from homeassistant.components.device_tracker.config_entry import (
    NetworkDeviceTrackerEntity)
import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_VERIFY_SSL,
    CONF_MONITORED_CONDITIONS)
import homeassistant.util.dt as dt_util

from .const import CONF_CONTROLLER, CONF_SITE_ID, CONTROLLER_ID

LOGGER = logging.getLogger(__name__)
CONF_PORT = 'port'
CONF_DT_SITE_ID = 'site_id'
CONF_DETECTION_TIME = 'detection_time'
CONF_SSID_FILTER = 'ssid_filter'

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 8443
DEFAULT_VERIFY_SSL = True
DEFAULT_DETECTION_TIME = timedelta(seconds=300)

TIMESTAMP_ATTRS = ['first_seen', 'last_seen', 'latest_assoc_time']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_DT_SITE_ID, default='default'): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): vol.Any(
        cv.boolean, cv.isfile),
    vol.Optional(CONF_DETECTION_TIME, default=DEFAULT_DETECTION_TIME): vol.All(
        cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_MONITORED_CONDITIONS): vol.All(cv.ensure_list),
    vol.Optional(CONF_SSID_FILTER): vol.All(cv.ensure_list, [cv.string])
})


async def async_setup_scanner(hass, config, sync_see, discovery_info):
    """Set up the Unifi integration."""
    if not hass.config_entries.async_entries(unifi.DOMAIN):
        hass.async_create_task(hass.config_entries.flow.async_init(
            unifi.DOMAIN, context={'source': config_entries.SOURCE_IMPORT},
            data=config
        ))
    return True


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up device tracker for UniFi component."""
    # return True
    controller_id = CONTROLLER_ID.format(
        host=config_entry.data[CONF_CONTROLLER][CONF_HOST],
        site=config_entry.data[CONF_CONTROLLER][CONF_SITE_ID],
    )
    controller = hass.data[unifi.DOMAIN][controller_id]
    tracked = {}

    progress = None

    async def request_update(object_id):
        """Request an update."""
        nonlocal progress

        if progress is not None:
            return await progress

        progress = asyncio.ensure_future(update_controller())
        result = await progress
        progress = None
        return result

    async def update_controller():
        """Update the values of the controller."""
        tasks = [async_update_items(
            controller, async_add_entities, request_update, tracked
        )]
        await asyncio.wait(tasks)

    await update_controller()


async def async_update_items(
        controller, async_add_entities, request_controller_update, tracked):
    """Update POE port state from the controller."""
    try:
        with async_timeout.timeout(4):
            await controller.api.clients.update()
            await controller.api.devices.update()

    except aiounifi.LoginRequired:
        try:
            with async_timeout.timeout(5):
                await controller.api.login()

        except (asyncio.TimeoutError, aiounifi.AiounifiException):
            if controller.available:
                controller.available = False
                # update_switch_state()
            return

    except (asyncio.TimeoutError, aiounifi.AiounifiException):
        if controller.available:
            LOGGER.error('Unable to reach controller %s', controller.host)
            controller.available = False
            # update_switch_state()
        return

    if not controller.available:
        LOGGER.info('Reconnected to controller %s', controller.host)
        controller.available = True

    new_tracked = []
    for client_id in controller.api.clients:

        if client_id in tracked:
            LOGGER.debug("Updating UniFi tracked device %s (%s)",
                         tracked[client_id].entity_id,
                         tracked[client_id].client.mac)
            tracked[client_id].async_schedule_update_ha_state()
            continue

        # if self.client.essid not in self.controller.ssid_filter:
        #     continue

        client = controller.api.clients[client_id]

        tracked[client_id] = UniFiClientTracker(
            client, controller, request_controller_update)
        new_tracked.append(tracked[client_id])
        LOGGER.debug("New UniFi switch %s (%s)", client.hostname, client.mac)

    if new_tracked:
        async_add_entities(new_tracked)


class UniFiClientTracker(NetworkDeviceTrackerEntity):
    """Representation of a network device."""

    def __init__(self, client, controller, request_controller_update):
        """Set up tracked device."""
        self.client = client
        self.controller = controller
        self.async_request_controller_update = request_controller_update

    async def async_update(self):
        """Synchronize state with controller."""
        await self.async_request_controller_update(self.client.mac)
        await self.async_see()

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self.client.name or self.client.hostname

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this switch."""
        return 'unifi-dt-{}'.format(self.client.mac)

    @property
    def available(self) -> bool:
        """Return if controller is available."""
        return self.controller.available

    @property
    def last_seen(self) -> dt_util.dt.datetime:
        """Return the timestamp when device was last seen."""
        return dt_util.utc_from_timestamp(float(self.client.last_seen))

    @property
    def device_state_attributes(self) -> dict:
        """Return the device state attributes."""
        attributes = {}
        for variable in self.client.raw:
            if variable in TIMESTAMP_ATTRS:
                attributes[variable] = dt_util.utc_from_timestamp(
                    float(self.client.raw[variable])
                )
            else:
                attributes[variable] = self.client.raw[variable]

        return attributes
