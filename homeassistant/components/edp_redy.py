"""
Support for EDP re:dy.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/edp_redy/
"""

import aiohttp
import asyncio
import json
import logging

import async_timeout
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
EDP_REDY = "edp_redy"
DATA_UPDATE_TOPIC = '{0}_data_update'.format(DOMAIN)
ACTIVE_POWER_ID = "home_active_power"

URL_BASE = "https://redy.edp.pt/EdpPortal/"
URL_LOGIN_PAGE = URL_BASE
URL_GET_ACTIVE_POWER = "{0}/Consumption/GetActivePower".format(URL_BASE)
URL_GET_SWITCH_MODULES = "{0}/HomeAutomation/GetSwitchModules".format(URL_BASE)
URL_SET_STATE_VAR = "{0}/HomeAutomation/SetStateVar".format(URL_BASE)
URL_LOGOUT = "{0}/Login/Logout".format(URL_BASE)

UPDATE_INTERVAL = 30
DEFAULT_TIMEOUT = 30
SESSION_TIME = 59

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


class EdpRedySession:
    """Representation of an http session to the service."""

    def __init__(self, hass, username, password):
        """Init the session."""
        self._username = username
        self._password = password
        self._session = None
        self._session_time = dt_util.utcnow()
        self._hass = hass
        self.modules_dict = {}
        self.values_dict = {}

    async def async_init_session(self):
        """Create a new http session."""
        payload_auth = {'username': self._username,
                        'password': self._password,
                        'screenWidth': '1920', 'screenHeight': '1080'}

        try:
            # create session and fetch login page
            session = aiohttp_client.async_get_clientsession(self._hass)
            with async_timeout.timeout(DEFAULT_TIMEOUT, loop=self._hass.loop):
                resp = await session.get(URL_LOGIN_PAGE)

        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error while accessing login page")
            return None

        if resp.status != 200:
            _LOGGER.error("Login page returned status code %s", resp.status)
            return None

        try:
            with async_timeout.timeout(DEFAULT_TIMEOUT, loop=self._hass.loop):
                resp = await session.post(URL_LOGIN_PAGE, data=payload_auth)

        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error while doing login post")
            return None

        if resp.status != 200:
            _LOGGER.error("Login post returned status code %s", resp.status)
            return None

        return session

    async def async_logout(self):
        """Logout from the current session."""
        _LOGGER.debug("Logout")

        try:
            with async_timeout.timeout(DEFAULT_TIMEOUT, loop=self._hass.loop):
                resp = await self._session.get(URL_LOGOUT)

        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error while doing logout")
            return False

        if resp.status != 200:
            _LOGGER.error("Logout returned status code %s", resp.status)
            return False

        return True

    async def async_validate_session(self):
        """Check the current session and create a new one if needed."""
        if self._session is not None:
            session_life = dt_util.utcnow() - self._session_time
            if session_life.total_seconds() < SESSION_TIME:
                """ Session valid, nothing to do """
                return True

            """ Session is older than SESSION_TIME: logout """
            await self.async_logout()
            self._session = None

        """ not valid, create new session """
        self._session = await self.async_init_session()
        self._session_time = dt_util.utcnow()
        return True if self._session is not None else False

    async def async_fetch_active_power(self):
        """Fetch new data from the server."""
        if not await self.async_validate_session():
            return False

        try:
            with async_timeout.timeout(DEFAULT_TIMEOUT, loop=self._hass.loop):
                resp = await self._session.post(URL_GET_ACTIVE_POWER)
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error while getting active power")
            return False
        if resp.status != 200:
            _LOGGER.error("Getting active power returned status code %s",
                          resp.status)
            return False

        active_power_str = await resp.text()
        _LOGGER.debug("Fetched Active Power:\n" + active_power_str)

        if active_power_str is None:
            return False

        try:
            updated_dict = json.loads(active_power_str)
        except (json.decoder.JSONDecodeError, TypeError):
            _LOGGER.error("Error parsing active power json. Received: \n %s",
                          active_power_str)
            return False

        if "Body" not in updated_dict:
            return False
        if "ActivePower" not in updated_dict["Body"]:
            return False

        try:
            self.values_dict[ACTIVE_POWER_ID] = \
                updated_dict["Body"]["ActivePower"] * 1000
        except ValueError:
            _LOGGER.error(
                "Could not parse value: ActivePower")
            self.values_dict[ACTIVE_POWER_ID] = None

        return True

    async def async_fetch_modules(self):
        """Fetch new data from the server."""
        if not await self.async_validate_session():
            return False

        try:
            with async_timeout.timeout(DEFAULT_TIMEOUT, loop=self._hass.loop):
                resp = await self._session.post(URL_GET_SWITCH_MODULES,
                                                data={"filter": 1})
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error while getting switch modules")
            return False
        if resp.status != 200:
            _LOGGER.error("Getting switch modules returned status code %s",
                          resp.status)
            return False

        modules_str = await resp.text()
        _LOGGER.debug("Fetched Modules:\n" + modules_str)

        if modules_str is None:
            return False

        try:
            updated_dict = json.loads(modules_str)
        except (json.decoder.JSONDecodeError, TypeError):
            _LOGGER.error("Error parsing modules json. Received: \n %s",
                          modules_str)
            return False

        if "Body" not in updated_dict:
            return False
        if "Modules" not in updated_dict["Body"]:
            return False

        for module in updated_dict["Body"]["Modules"]:
            self.modules_dict[module['PKID']] = module

        return True

    async def async_update(self):
        """Get data from the server and update local structures."""
        modules_success = await self.async_fetch_modules()
        active_power_success = await self.async_fetch_active_power()

        return modules_success and active_power_success

    async def async_set_state_var(self, json_payload):
        """Call SetStateVar API on the server."""
        if not await self.async_validate_session():
            return False

        _LOGGER.debug("Calling %s with: %s", URL_SET_STATE_VAR,
                      str(json_payload))

        try:
            with async_timeout.timeout(DEFAULT_TIMEOUT, loop=self._hass.loop):
                resp = await self._session.post(URL_SET_STATE_VAR,
                                                json=json_payload)
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error while setting state var")
            return False
        if resp.status != 200:
            _LOGGER.error("Setting state var returned status code %s",
                          resp.status)
            return False

        return True


async def async_setup(hass, config):
    """Set up the EDP re:dy component."""
    session = EdpRedySession(hass, config[DOMAIN][CONF_USERNAME],
                             config[DOMAIN][CONF_PASSWORD])
    hass.data[EDP_REDY] = session
    platform_loaded = False

    async def async_update_and_sched(time):
        update_success = await session.async_update()

        if update_success:
            dispatcher.async_dispatcher_send(hass, DATA_UPDATE_TOPIC)

            nonlocal platform_loaded
            if not platform_loaded:
                for component in ['sensor', 'switch']:
                    await discovery.async_load_platform(hass, component,
                                                        DOMAIN, {}, config)
                platform_loaded = True

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
        self._name = name if len(name) > 0 else device_id

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
                self._is_available = not data["OutOfOrder"]
            except ValueError:
                _LOGGER.error(
                    "Could not parse OutOfOrder for %s", self._id)
                self._is_available = False
