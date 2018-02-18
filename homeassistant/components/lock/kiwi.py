"""
Support for the KIWI.KI lock platform.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/lock.kiwi/
"""
import logging
import requests

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.util.dt import (utcnow, parse_datetime)
from homeassistant.components.lock import (LockDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_PASSWORD, CONF_USERNAME, ATTR_ID, ATTR_LONGITUDE, ATTR_LATITUDE)


_LOGGER = logging.getLogger(__name__)

ATTR_TYPE = 'hardware_type'
ATTR_PERMISSION = 'permission'
ATTR_CAN_INVITE = 'can_invite_others'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string
})

BASE_URL = 'https://api.kiwi.ki'
API_AUTH_URL = BASE_URL + '/pre/session/'
API_LIST_DOOR_URL = BASE_URL + '/pre/sensors/'
API_OPEN_DOOR_URL = BASE_URL + '/pre/sensors/{}/act/open'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the KIWI lock platform."""
    kiwi = KiwiClient(config.get(CONF_USERNAME), config.get(CONF_PASSWORD))
    add_devices([KiwiLock(lock, kiwi) for lock in kiwi.get_locks()], True)


class KiwiClient:
    """Client for KIWI service."""

    def __init__(self, username, password):
        """Initiale the client.

        :param username: valid KIWI username. Hint: your signup email address.
        :param password: your KIWI account password.
        """
        self.__username = username
        self.__password = password
        self.__session_key = None
        self.__session_expires = None

        # get a new session token on client startup
        self._renew_sessionkey()

    def _with_valid_session(self):
        """Check if the session is valid; renew if necessary."""
        if not self.__session_expires or (utcnow() >= self.__session_expires):
            _LOGGER.debug("no valid session found - renewing session key")
            self._renew_sessionkey()

    def _renew_sessionkey(self):
        """Update the clients session key."""
        _LOGGER.info(
            "authentication for user %s started.",
            self.__username)

        auth_response = requests.post(
            API_AUTH_URL,
            json={
                "username": self.__username,
                "password": self.__password
            },
            headers={"Accept": "application/json"}
        )

        if not auth_response.ok:
            _LOGGER.error(
                "could not authenticate at KIWI:\n%s",
                auth_response.json())

            raise ValueError("authentication failed")

        self.__session_key = auth_response.json()['result']['session_key']
        self.__session_expires = parse_datetime(
            auth_response.json()['result']['session']['expires'])

    def get_locks(self):
        """Return a list of kiwi locks."""
        self._with_valid_session()
        sensor_list = requests.get(
            API_LIST_DOOR_URL,
            params={"session_key": self.__session_key},
            headers={"Accept": "application/json"}
        )
        if not sensor_list.ok:
            _LOGGER.error("could not get your KIWI doors.")
            return []

        doors = sensor_list.json()['result']['sensors']
        return doors

    def open_door(self, door_id):
        """Open the kiwi door lock."""
        self._with_valid_session()
        open_response = requests.post(
            API_OPEN_DOOR_URL.format(door_id),
            headers={"Accept": "application/json"},
            params={"session_key": self.__session_key}
        )
        return True if open_response.ok else False


class KiwiLock(LockDevice):
    """Representation of a Kiwi lock."""

    def __init__(self, kiwi_lock, client):
        """Initialize the lock."""
        self._sensor = kiwi_lock
        self._device_attrs = None
        self._client = client
        self.lock_id = kiwi_lock['sensor_id']

        address = kiwi_lock.get('address')
        lat = address.pop('lat', None)
        lng = address.pop('lng', None)

        self._device_attrs = {
            ATTR_ID: self.lock_id,
            ATTR_TYPE: kiwi_lock.get('hardware_type'),
            ATTR_PERMISSION: kiwi_lock.get('highest_permission'),
            ATTR_CAN_INVITE: kiwi_lock.get('can_invite')}

        self._device_attrs.update(address)
        self._device_attrs.update({
            ATTR_LATITUDE: lat,
            ATTR_LONGITUDE: lng
        })

    @property
    def name(self):
        """Return the name of the lock."""
        name = self._sensor.get('name')
        specifier = self._sensor['address'].get('specifier')
        return name or specifier

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return True

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        return self._device_attrs

    def unlock(self, **kwargs):
        """Unlock the device."""
        if not self._client.open_door(self.lock_id):
            _LOGGER.error("failed to open door")
