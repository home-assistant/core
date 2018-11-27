"""
Support for EDP re:dy.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/edp_redy/
"""

import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD,
                                 EVENT_HOMEASSISTANT_START)
from homeassistant.core import callback
from homeassistant.helpers import discovery, dispatcher, aiohttp_client
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'edp_redy'
EDP_REDY = 'edp_redy'
DATA_UPDATE_TOPIC = '{0}_data_update'.format(DOMAIN)
UPDATE_INTERVAL = 60

REQUIREMENTS = ['edp_redy==0.0.2']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the EDP re:dy component."""
    from edp_redy import EdpRedySession

    session = EdpRedySession(config[DOMAIN][CONF_USERNAME],
                             config[DOMAIN][CONF_PASSWORD],
                             aiohttp_client.async_get_clientsession(hass),
                             hass.loop)
    hass.data[EDP_REDY] = session
    platform_loaded = False

    async def async_update_and_sched(time):
        update_success = await session.async_update()

        if update_success:
            nonlocal platform_loaded
            # pylint: disable=used-before-assignment
            if not platform_loaded:
                for component in ['sensor', 'switch']:
                    await discovery.async_load_platform(hass, component,
                                                        DOMAIN, {}, config)
                platform_loaded = True

            dispatcher.async_dispatcher_send(hass, DATA_UPDATE_TOPIC)

        # schedule next update
        async_track_point_in_time(hass, async_update_and_sched,
                                  time + timedelta(seconds=UPDATE_INTERVAL))

    async def start_component(event):
        _LOGGER.debug("Starting updates")
        await async_update_and_sched(dt_util.utcnow())

    # only start fetching data after HA boots to prevent delaying the boot
    # process
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_component)

    return True


class EdpRedyDevice(Entity):
    """Representation a base re:dy device."""

    def __init__(self, session, device_id, name):
        """Initialize the device."""
        self._session = session
        self._state = None
        self._is_available = True
        self._device_state_attributes = {}
        self._id = device_id
        self._unique_id = device_id
        self._name = name if name else device_id

    async def async_added_to_hass(self):
        """Subscribe to the data updates topic."""
        dispatcher.async_dispatcher_connect(
            self.hass, DATA_UPDATE_TOPIC, self._data_updated)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def available(self):
        """Return True if entity is available."""
        return self._is_available

    @property
    def should_poll(self):
        """Return the polling state. No polling needed."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._device_state_attributes

    @callback
    def _data_updated(self):
        """Update state, trigger updates."""
        self.async_schedule_update_ha_state(True)

    def _parse_data(self, data):
        """Parse data received from the server."""
        if "OutOfOrder" in data:
            try:
                self._is_available = not data['OutOfOrder']
            except ValueError:
                _LOGGER.error(
                    "Could not parse OutOfOrder for %s", self._id)
                self._is_available = False
