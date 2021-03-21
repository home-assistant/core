"""Component for interacting with the Yale Smart Alarm System API."""
import logging

import voluptuous as vol
from yalesmartalarmclient.client import (
    AuthenticationError,
    YaleSmartAlarmClient,
)

from homeassistant.components.lock import (
    PLATFORM_SCHEMA,
    LockEntity,
)
from homeassistant.const import (
    ATTR_CODE,
    STATE_LOCKED,
    STATE_UNLOCKED,
    STATE_UNAVAILABLE,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_CODE,
)

import homeassistant.helpers.config_validation as cv

CONF_AREA_ID = "area_id"

DEFAULT_NAME = "Yale Smart Alarm"

DEFAULT_AREA_ID = "1"

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_AREA_ID, default=DEFAULT_AREA_ID): cv.string,
        vol.Optional(CONF_CODE): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the alarm platform."""
    name = config[CONF_NAME]
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    area_id = config[CONF_AREA_ID]
    code = config[CONF_CODE]

    try:
        client = YaleSmartAlarmClient(username, password, area_id)
    except AuthenticationError:
        _LOGGER.error("Authentication failed. Check credentials")
        return

    lockdevices = []
    locks = client.lock_api.locks()
    for lock in locks:
        lockdevices.append(YaleDoorlock(lock, client, code))

    if lockdevices is not None and lockdevices != []:
        add_entities(lockdevices)
    else:
        return False

    return True


class YaleDoorlock(LockEntity):
    """Representation of a Yale doorlock."""

    def __init__(self, lock, client, code):
        """Initialize the Yale Alarm Device."""
        self._name = lock.name
        self._lock = lock
        self._client = client
        self._state = None
        self._code = code

        self._state_map = {
            1: STATE_LOCKED,
            2: STATE_UNLOCKED,
            3: STATE_UNLOCKED,
            4: STATE_UNAVAILABLE,
        }

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def is_locked(self):
        return self._state == STATE_LOCKED

    def update(self):
        """Return the state of the device."""
        lock_status = self._client.lock_api.get(self._name)._state._value_

        self._state = self._state_map.get(lock_status)

    def unlock(self, **kwargs) -> None:
        """Send unlock command."""
        code = kwargs.get(ATTR_CODE, self._code)
        if code is None:
            LOGGER.error("Code required but none provided")
            return

        self._client.lock_api.open_lock(self._lock, pin_code=code)

    def lock(self, **kwargs) -> None:
        """Send lock command."""
        code = kwargs.get(ATTR_CODE, self._code)
        if code is None:
            LOGGER.error("Code required but none provided")
            return

        self._client.lock_api.close_lock(self._lock, pin_code=code)
