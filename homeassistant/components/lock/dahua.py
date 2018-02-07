"""
Dahua Camera Station lock (VTO2000A).

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/lock.dahua/
"""
import asyncio
import logging
import requests

import voluptuous as vol

from homeassistant.components.lock import LockDevice
from homeassistant.components.camera import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_USERNAME, CONF_PASSWORD)
import homeassistant.helpers.config_validation as cv

DOMAIN = "dahua"

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = []

DEFAULT_NAME = 'Dahua Camera Lock'
DEFAULT_USERNAME = 'admin'
DEFAULT_PASSWORD = '888888'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
    vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up a Dahua Camera Lock."""
    async_add_devices([Dahua(hass, config)])


class Dahua(LockDevice):
    """An implementation of an Dahua camera lock."""

    def __init__(self, hass, config):
        """Initialize a Dahua Lock."""
        self._name = config.get(CONF_NAME)
        self._url = "http://{}".format(config.get(CONF_HOST))
        self._session = requests.Session()
        self._state = True
        payload_homepage = dict(
            method="global.login",
            params=dict(userName=config.get(CONF_USERNAME), password="",
                        clientType="Web3.0"),
            id=1,
            session=0
        )
        response = self._session.post("{}/RPC2_Login".format(self._url),
                                      json=payload_homepage).json()
        self._session_id = response.get("session")
        cookie = "DhWebClientSessionID=%s" % self._session_id
        self._session.headers["Cookie"] = cookie
        _LOGGER.debug("%s: URL %s session_id=%s",
                      self._name, self._url, self._session_id)
        payload_login = dict(
            method="global.login",
            params=dict(
                userName=config.get(CONF_USERNAME),
                password=config.get(CONF_PASSWORD),
                clientType="Web3.0", passwordType="Default",
                realm=response.get("params").get("realm"),
                random=response.get("params").get("realm"),
            ),
            id=2,
            session=self._session_id
        )
        response = self._session.post("{}/RPC2_Login".format(self._url),
                                      json=payload_login).json()
        _LOGGER.debug("%s: logged=%s",
                      self._name, response.get("result"))

    @asyncio.coroutine
    def async_unlock(self, **kwargs):
        """Open door."""
        try:
            payload_object_id = dict(
                method="accessControl.factory.instance",
                params=dict(channel=0),
                id=3,
                session=self._session_id
            )
            response = self._session.post("{}/RPC2".format(self._url),
                                          json=payload_object_id).json()
            payload_open = dict(
                method="accessControl.openDoor",
                params=dict(Type="Remote"),
                id=4,
                session=self._session_id,
                object=response.get("result")
            )
            response = self._session.post("{}/RPC2".format(self._url),
                                          json=payload_open).json()
            _LOGGER.debug("%s: unlock=%s",
                          self._name, response.get("result"))

            self._state = response.get("result")
        except requests.exceptions.RequestException as error:
            _LOGGER.error("error unlocking: %s", error)
            return None

        return self._state

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the lock."""
        return self._name

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return self._state
