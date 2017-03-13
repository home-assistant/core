"""

Interfaces with Alarm.com alarm control panels.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.alarmdotcom/
"""
import logging
import re
import asyncio
import voluptuous as vol
import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.alarm_control_panel import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_PASSWORD, CONF_USERNAME, STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED, STATE_UNKNOWN, CONF_CODE,
    CONF_NAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import aiohttp
import async_timeout

REQUIREMENTS = ['beautifulsoup4==4.5.3']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Alarm.com'

# Alarm.com constants
# Alarm.com baseURL
ALARMDOTCOM_URL = 'https://www.alarm.com/pda/'

# First get the session URL that wil be needed to
SESSION_KEY_RE = re.compile(
    '{url}(?P<sessionKey>.*)/Default.aspx'.format(url=ALARMDOTCOM_URL))

# ALARM.COM CSS MAPPINGS
USERNAME = 'ctl00$ContentPlaceHolder1$txtLogin'
PASSWORD = 'ctl00$ContentPlaceHolder1$txtPassword'

LOGIN_CONST = 'ctl00$ContentPlaceHolder1$btnLogin'

ERROR_CONTROL = 'ctl00_ContentPlaceHolder1_ErrorControl1'
MESSAGE_CONTROL = 'ctl00_ErrorControl1'

VIEWSTATE = '__VIEWSTATE'
VIEWSTATEGENERATOR = '__VIEWSTATEGENERATOR'
VIEWSTATEENCRYPTED = '__VIEWSTATEENCRYPTED'

EVENTVALIDATION = '__EVENTVALIDATION'
DISARM_EVENT_VALIDATION = \
    'MnXvTutfO7KZZ1zZ7QR19E0sfvOVCpK7SV' \
    'yeJ0IkUkbXpfEqLa4fa9PzFK2ydqxNal'
ARM_STAY_EVENT_VALIDATION = \
    '/CwyHTpKH4aUp/pqo5gRwFJmKGubsvmx3RI6n' \
    'IFcyrtacuqXSy5dMoqBPX3aV2ruxZBTUVxenQ' \
    '7luwjnNdcsxQW/p+YvHjN9ialbwACZfQsFt2o5'
ARM_AWAY_EVENT_VALIDATION = '3ciB9sbTGyjfsnXn7J4LjfBvdGlkqiHoeh1vPjc5'

DISARM_COMMAND = 'ctl00$phBody$butDisarm'
ARM_STAY_COMMAND = 'ctl00$phBody$butArmStay'
ARM_AWAY_COMMAND = 'ctl00$phBody$butArmAway'

ARMING_PANEL = '#ctl00_phBody_pnlArming'
ALARM_STATE = '#ctl00_phBody_lblArmingState'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Optional(CONF_CODE): cv.positive_int,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

COMMAND_LIST = {'Disarm': {'command': DISARM_COMMAND,
                           'eventvalidation': DISARM_EVENT_VALIDATION},
                'Arm+Stay': {'command': ARM_STAY_COMMAND,
                             'eventvalidation': ARM_STAY_EVENT_VALIDATION},
                'Arm+Away': {'command': ARM_AWAY_COMMAND,
                             'eventvalidation': ARM_AWAY_EVENT_VALIDATION}}


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup a Alarm.com control panel."""
    name = config.get(CONF_NAME)
    code = config.get(CONF_CODE)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    alarmdotcom = AlarmDotCom(hass, name, code, username, password)
    yield from alarmdotcom.async_login()
    async_add_devices([alarmdotcom])


class AlarmDotCom(alarm.AlarmControlPanel):
    """Represent an Alarm.com status."""

    def __init__(self, hass, name, code, username, password):
        """Initialize the Alarm.com status."""
        _LOGGER.debug('Setting up Alarm.com...')
        self._hass = hass
        self._name = name
        self._code = str(code) if code else None
        self._username = username
        self._password = password
        self._websession = async_get_clientsession(self._hass)
        self._login_info = None
        self._state = STATE_UNKNOWN

    @asyncio.coroutine
    def async_login(self):
        """Login to Alarm.com."""
        _LOGGER.debug('Attempting to log into Alarm.com...')
        from bs4 import BeautifulSoup

        # Get the session key for future logins.
        response = None
        try:
            with async_timeout.timeout(10, loop=self._hass.loop):
                response = yield from self._websession.get(
                    ALARMDOTCOM_URL + '/Default.aspx')

            _LOGGER.debug(
                'Response status from Alarm.com: %s',
                response.status)
            text = yield from response.text()
            _LOGGER.debug(text)
            tree = BeautifulSoup(text, 'html.parser')
            self._login_info = {
                'sessionkey': SESSION_KEY_RE.match(
                    response.url).groupdict()['sessionKey'],
                VIEWSTATE: tree.select(
                    '#{}'.format(VIEWSTATE))[0].attrs.get('value'),
                VIEWSTATEGENERATOR: tree.select(
                    '#{}'.format(VIEWSTATEGENERATOR))[0].attrs.get('value'),
                EVENTVALIDATION: tree.select(
                    '#{}'.format(EVENTVALIDATION))[0].attrs.get('value')
            }

            _LOGGER.debug(self._login_info)
            _LOGGER.info('Successful login to Alarm.com')

        except (asyncio.TimeoutError, aiohttp.errors.ClientError):
            _LOGGER.error('Can not get login page from Alarm.com')
            return False
        except AttributeError:
            _LOGGER.error('Unable to get sessionKey from Alarm.com')
            raise

        # Login params to pass during the post
        params = {
            USERNAME: self._username,
            PASSWORD: self._password,
            VIEWSTATE: self._login_info[VIEWSTATE],
            VIEWSTATEGENERATOR: self._login_info[VIEWSTATEGENERATOR],
            EVENTVALIDATION: self._login_info[EVENTVALIDATION]
        }

        try:
            # Make an attempt to log in.
            with async_timeout.timeout(10, loop=self._hass.loop):
                response = yield from self._websession.post(
                    ALARMDOTCOM_URL + '{}/Default.aspx'.format(
                        self._login_info['sessionkey']),
                    data=params)
            _LOGGER.debug(
                'Status from Alarm.com login %s', response.status)

            # Get the text from the login to ensure that we are logged in.
            text = yield from response.text()
            _LOGGER.debug(text)
            tree = BeautifulSoup(text, 'html.parser')
            try:
                # Get the initial state.
                self._state = tree.select(ALARM_STATE)[0].get_text()
                _LOGGER.debug(
                    'Current alarm state: %s', self._state)
            except IndexError:
                try:
                    error_control = tree.select(
                        '#{}'.format(ERROR_CONTROL))[0].attrs.get('value')
                    if 'Login failure: Bad Credentials' in error_control:
                        _LOGGER.error(error_control)
                        return False
                except AttributeError:
                    _LOGGER.error('Error while trying to log into Alarm.com')
                    return False
        except (asyncio.TimeoutError, aiohttp.errors.ClientError):
            _LOGGER.error("Can not load login page from Alarm.com")
            return False

    @asyncio.coroutine
    def async_update(self):
        """Fetch the latest state."""
        _LOGGER.debug('Calling update on Alarm.com')
        from bs4 import BeautifulSoup
        response = None
        if not self._login_info:
            yield from self.async_login()
        try:
            with async_timeout.timeout(10, loop=self._hass.loop):
                response = yield from self._websession.get(
                    ALARMDOTCOM_URL + '{}/main.aspx'.format(
                        self._login_info['sessionkey']))

            _LOGGER.debug('Response from Alarm.com: %s', response.status)
            text = yield from response.text()
            _LOGGER.debug(text)
            tree = BeautifulSoup(text, 'html.parser')
            try:
                self._state = tree.select(ALARM_STATE)[0].get_text()
                _LOGGER.debug(
                    'Current alarm state: %s', self._state)
            except IndexError:
                # We may have timed out. Re-login again
                yield from self.async_login()
        except (asyncio.TimeoutError, aiohttp.errors.ClientError):
            _LOGGER.error("Can not load login page from Alarm.com")
            return False
        finally:
            if response is not None:
                yield from response.release()

    @property
    def name(self):
        """Return the name of the alarm."""
        return self._name

    @property
    def code_format(self):
        """One or more characters if code is defined."""
        return None if self._code is None else '.+'

    @property
    def state(self):
        """Return the state of the device."""
        if self._state.lower() == 'disarmed':
            return STATE_ALARM_DISARMED
        elif self._state.lower() == 'armed stay':
            return STATE_ALARM_ARMED_HOME
        elif self._state.lower() == 'armed away':
            return STATE_ALARM_ARMED_AWAY
        else:
            return STATE_UNKNOWN

    @asyncio.coroutine
    def _send(self, event, code):
        _LOGGER.debug('Sending %s to Alarm.com', event)
        from bs4 import BeautifulSoup
        if not self._validate_code(code):
            return

        with async_timeout.timeout(10, loop=self._hass.loop):
            try:
                response = yield from self._websession.post(
                    ALARMDOTCOM_URL + '{}/main.aspx'.format(
                        self._login_info['sessionkey']),
                    data={
                        VIEWSTATE: '',
                        VIEWSTATEENCRYPTED: '',
                        EVENTVALIDATION:
                            COMMAND_LIST[event]['eventvalidation'],
                        COMMAND_LIST[event]['command']: event})

                _LOGGER.debug(
                    'Response from Alarm.com %s', response.status)
                text = yield from response.text()
                tree = BeautifulSoup(text, 'html.parser')
                try:
                    message = tree.select(
                        '#{}'.format(MESSAGE_CONTROL))[0].get_text()
                    if 'command' in message:
                        _LOGGER.debug(message)
                        # Update alarm.com status after calling state change.
                        yield from self.async_update()
                except IndexError:
                    # May have been logged out
                    self.async_login()
                    if event == 'Disarm':
                        yield from self.async_alarm_disarm(code=code)
                    elif event == 'Arm+Stay':
                        yield from self.async_alarm_arm_away(code=code)
                    elif event == 'Arm+Away':
                        yield from self.async_alarm_arm_away(code=code)

            except (asyncio.TimeoutError, aiohttp.errors.ClientError):
                _LOGGER.error('Error while trying to disarm Alarm.com system')

    @asyncio.coroutine
    def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        yield from self._send('Disarm', code)

    @asyncio.coroutine
    def async_alarm_arm_home(self, code=None):
        """Send arm hom command."""
        yield from self._send('Arm+Stay', code)

    @asyncio.coroutine
    def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        yield from self._send('Arm+Away', code)

    def _validate_code(self, code):
        """Validate given code."""
        check = self._code is None or code == self._code
        if not check:
            _LOGGER.warning('Wrong code entered.')
        return check
