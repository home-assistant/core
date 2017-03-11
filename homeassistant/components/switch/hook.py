"""
Support Hook, available at hooksmarthome.com.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.hook/
"""
import logging
import asyncio

import voluptuous as vol
import async_timeout
import aiohttp

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

HOOK_ENDPOINT = 'https://api.gethook.io/v1/'
TIMEOUT = 10

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up Hook by getting the access token and list of actions."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    websession = async_get_clientsession(hass)

    response = None
    try:
        with async_timeout.timeout(TIMEOUT, loop=hass.loop):
            response = yield from websession.post(
                '{}{}'.format(HOOK_ENDPOINT, 'user/login'),
                data={
                    'username': username,
                    'password': password})
        data = yield from response.json()
    except (asyncio.TimeoutError,
            aiohttp.errors.ClientError,
            aiohttp.errors.ClientDisconnectedError) as error:
        _LOGGER.error("Failed authentication API call: %s", error)
        return False
    finally:
        if response is not None:
            yield from response.release()

    try:
        token = data['data']['token']
    except KeyError:
        _LOGGER.error("No token. Check username and password")
        return False

    response = None
    try:
        with async_timeout.timeout(TIMEOUT, loop=hass.loop):
            response = yield from websession.get(
                '{}{}'.format(HOOK_ENDPOINT, 'device'),
                params={"token": data['data']['token']})
        data = yield from response.json()
    except (asyncio.TimeoutError,
            aiohttp.errors.ClientError,
            aiohttp.errors.ClientDisconnectedError) as error:
        _LOGGER.error("Failed getting devices: %s", error)
        return False
    finally:
        if response is not None:
            yield from response.release()

    async_add_devices(
        HookSmartHome(
            hass,
            token,
            d['device_id'],
            d['device_name'])
        for lst in data['data']
        for d in lst)


class HookSmartHome(SwitchDevice):
    """Representation of a Hook device, allowing on and off commands."""

    def __init__(self, hass, token, device_id, device_name):
        """Initialize the switch."""
        self.hass = hass
        self._token = token
        self._state = False
        self._id = device_id
        self._name = device_name
        _LOGGER.debug(
            "Creating Hook object: ID: %s  Name: %s", self._id, self._name)

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @asyncio.coroutine
    def _send(self, url):
        """Send the url to the Hook API."""
        response = None
        try:
            _LOGGER.debug("Sending: %s", url)
            websession = async_get_clientsession(self.hass)
            with async_timeout.timeout(TIMEOUT, loop=self.hass.loop):
                response = yield from websession.get(
                    url, params={"token": self._token})
            data = yield from response.json()

        except (asyncio.TimeoutError,
                aiohttp.errors.ClientError,
                aiohttp.errors.ClientDisconnectedError) as error:
            _LOGGER.error("Failed setting state: %s", error)
            return False

        finally:
            if response is not None:
                yield from response.release()

        _LOGGER.debug("Got: %s", data)
        return data['return_value'] == '1'

    @asyncio.coroutine
    def async_turn_on(self):
        """Turn the device on asynchronously."""
        _LOGGER.debug("Turning on: %s", self._name)
        url = '{}{}{}{}'.format(
            HOOK_ENDPOINT, 'device/trigger/', self._id, '/On')
        success = yield from self._send(url)
        self._state = success

    @asyncio.coroutine
    def async_turn_off(self):
        """Turn the device off asynchronously."""
        _LOGGER.debug("Turning off: %s", self._name)
        url = '{}{}{}{}'.format(
            HOOK_ENDPOINT, 'device/trigger/', self._id, '/Off')
        success = yield from self._send(url)
        # If it wasn't successful, keep state as true
        self._state = not success
