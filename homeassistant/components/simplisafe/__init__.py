"""
Interfaces with SimpliSafe alarm control panel.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.simplisafe/
"""
import logging
import re

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.components.alarm_control_panel import (
    PLATFORM_SCHEMA, AlarmControlPanel)
from homeassistant.const import (
    CONF_CODE, CONF_NAME, CONF_PASSWORD, CONF_USERNAME, STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED)
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.util.json import load_json, save_json

from .config_flow import configured_instances
from .const import DATA_SIMPLISAFE_CLIENT, DATA_SIMPLISAFE_LISTENER, DOMAIN

REQUIREMENTS = ['simplisafe-python==3.1.1']

_LOGGER = logging.getLogger(__name__)

ATTR_ALARM_ACTIVE = "alarm_active"
ATTR_TEMPERATURE = "temperature"

DATA_SIMPLISAFE_LISTENER = 'data_simpli'
DATA_FILE = '.simplisafe'

DEFAULT_NAME = 'SimpliSafe'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_CODE): cv.string,
})


async def async_setup(hass, config):
    """Set up the SimpliSafe component."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_SIMPLISAFE_CLIENT] = {}
    hass.data[DOMAIN][DATA_SIMPLISAFE_LISTENER] = {}

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    if conf[CONF_USERNAME] not in configured_instances(hass):
        hass.async_add_job(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={'source': SOURCE_IMPORT},
                data={
                    CONF_USERNAME: conf[CONF_USERNAME],
                    CONF_PASSWORD: conf[CONF_PASSWORD],
                    CONF_NAME: conf[CONF_NAME],
                    CONF_CODE: conf[CONF_CODE],
                }))

    return True


async def async_setup_entry(hass, config_entry):
    """Set up OpenUV as config entry."""
    # from simplipy import API
    # from simplipy.errors import SimplipyError

    # try:
    #     websession = aiohttp_client.async_get_clientsession(hass)
    #     openuv = OpenUV(
    #         Client(
    #             config_entry.data[CONF_API_KEY],
    #             config_entry.data.get(CONF_LATITUDE, hass.config.latitude),
    #             config_entry.data.get(CONF_LONGITUDE, hass.config.longitude),
    #             websession,
    #             altitude=config_entry.data.get(
    #                 CONF_ELEVATION, hass.config.elevation)),
    #         config_entry.data.get(CONF_BINARY_SENSORS, {}).get(
    #             CONF_MONITORED_CONDITIONS, list(BINARY_SENSORS)),
    #         config_entry.data.get(CONF_SENSORS, {}).get(
    #             CONF_MONITORED_CONDITIONS, list(SENSORS)))
    #     await openuv.async_update()
    #     hass.data[DOMAIN][DATA_OPENUV_CLIENT][config_entry.entry_id] = openuv
    # except OpenUvError as err:
    #     _LOGGER.error('An error occurred: %s', str(err))
    #     hass.components.persistent_notification.create(
    #         'Error: {0}<br />'
    #         'You will need to restart hass after fixing.'
    #         ''.format(err),
    #         title=NOTIFICATION_TITLE,
    #         notification_id=NOTIFICATION_ID)
    #     return False

    for component in ('alarm_control_panel'):
        hass.async_create_task(hass.config_entries.async_forward_entry_setup(
            config_entry, component))

    async def refresh_sensors(event_time):
        """Refresh OpenUV data."""
        _LOGGER.debug('Refreshing OpenUV data')
        await openuv.async_update()
        async_dispatcher_send(hass, TOPIC_UPDATE)

    hass.data[DOMAIN][DATA_OPENUV_LISTENER][
        config_entry.entry_id] = async_track_time_interval(
            hass, refresh_sensors,
            hass.data[DOMAIN].get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

    return True
# async def async_setup_platform(
#         hass, config, async_add_entities, discovery_info=None):
#     """Set up the SimpliSafe platform."""

#     username = config[CONF_USERNAME]
#     password = config[CONF_PASSWORD]
#     name = config.get(CONF_NAME)
#     code = config.get(CONF_CODE)

#     websession = aiohttp_client.async_get_clientsession(hass)

#     config_data = await hass.async_add_executor_job(
#         load_json, hass.config.path(DATA_FILE))

#     try:
#         if config_data:
#             try:
#                 simplisafe = await API.login_via_token(
#                     config_data['refresh_token'], websession)
#                 _LOGGER.debug('Logging in with refresh token')
#             except SimplipyError:
#                 _LOGGER.info('Refresh token expired; attempting credentials')
#                 simplisafe = await API.login_via_credentials(
#                     username, password, websession)
#         else:
#             simplisafe = await API.login_via_credentials(
#                 username, password, websession)
#             _LOGGER.debug('Logging in with credentials')
#     except SimplipyError as err:
#         _LOGGER.error("There was an error during setup: %s", err)
#         return

#     config_data = {'refresh_token': simplisafe.refresh_token}
#     await hass.async_add_executor_job(
#         save_json, hass.config.path(DATA_FILE), config_data)

#     systems = await simplisafe.get_systems()
#     async_add_entities(
#         [SimpliSafeAlarm(system, name, code) for system in systems], True)


class SimpliSafeAlarm(AlarmControlPanel):
    """Representation of a SimpliSafe alarm."""

    def __init__(self, system, name, code):
        """Initialize the SimpliSafe alarm."""
        self._attrs = {}
        self._code = str(code) if code else None
        self._name = name
        self._system = system
        self._state = None

    @property
    def unique_id(self):
        """Return the unique ID."""
        return self._system.system_id

    @property
    def name(self):
        """Return the name of the device."""
        if self._name:
            return self._name
        return 'Alarm {}'.format(self._system.system_id)

    @property
    def code_format(self):
        """Return one or more digits/characters."""
        if not self._code:
            return None
        if isinstance(self._code, str) and re.search('^\\d+$', self._code):
            return 'Number'
        return 'Any'

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    def _validate_code(self, code, state):
        """Validate given code."""
        check = self._code is None or code == self._code
        if not check:
            _LOGGER.warning("Wrong code entered for %s", state)
        return check

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        if not self._validate_code(code, 'disarming'):
            return

        await self._system.set_off()

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        if not self._validate_code(code, 'arming home'):
            return

        await self._system.set_home()

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        if not self._validate_code(code, 'arming away'):
            return

        await self._system.set_away()

    async def async_update(self):
        """Update alarm status."""
        await self._system.update()

        if self._system.state == self._system.SystemStates.off:
            self._state = STATE_ALARM_DISARMED
        elif self._system.state in (
                self._system.SystemStates.home,
                self._system.SystemStates.home_count):
            self._state = STATE_ALARM_ARMED_HOME
        elif self._system.state in (
                self._system.SystemStates.away,
                self._system.SystemStates.away_count,
                self._system.SystemStates.exit_delay):
            self._state = STATE_ALARM_ARMED_AWAY
        else:
            self._state = None

        self._attrs[ATTR_ALARM_ACTIVE] = self._system.alarm_going_off
        if self._system.temperature:
            self._attrs[ATTR_TEMPERATURE] = self._system.temperature
