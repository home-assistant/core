"""
Nuki.io lock platform.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/lock.nuki/
"""
from datetime import timedelta
from os import path
import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.lock import (LockDevice, PLATFORM_SCHEMA)
from homeassistant.config import load_yaml_config_file
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_HOST, CONF_PORT, CONF_TOKEN)
from homeassistant.helpers.service import extract_entity_ids
from homeassistant.util import Throttle

REQUIREMENTS = ['pynuki==1.3.0']

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 8080

ATTR_BATTERY_CRITICAL = 'battery_critical'
ATTR_NUKI_ID = 'nuki_id'
ATTR_UNLATCH = 'unlatch'
DOMAIN = 'nuki'
SERVICE_LOCK_N_GO = 'nuki_lock_n_go'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Required(CONF_TOKEN): cv.string
})

LOCK_N_GO_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_UNLATCH, default=False): cv.boolean
})

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=30)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=5)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Nuki lock platform."""
    from pynuki import NukiBridge
    bridge = NukiBridge(config.get(CONF_HOST), config.get(CONF_TOKEN))
    add_devices([NukiLock(lock, hass) for lock in bridge.locks])

    def lock_n_go(service):
        """Service handler for nuki.lock_n_go."""
        unlatch = service.data.get(ATTR_UNLATCH, False)
        entity_ids = extract_entity_ids(hass, service)
        all_locks = hass.data[DOMAIN]['lock']
        target_locks = []
        if entity_ids is None:
            target_locks = all_locks
        else:
            for lock in all_locks:
                if lock.entity_id in entity_ids:
                    target_locks.append(lock)
        for lock in target_locks:
            lock.lock_n_go(unlatch=unlatch)

    descriptions = load_yaml_config_file(
        path.join(path.dirname(__file__), 'services.yaml'))

    hass.services.register(
        DOMAIN, SERVICE_LOCK_N_GO, lock_n_go,
        descriptions.get(SERVICE_LOCK_N_GO), schema=LOCK_N_GO_SERVICE_SCHEMA)


class NukiLock(LockDevice):
    """Representation of a Nuki lock."""

    def __init__(self, nuki_lock, hass):
        """Initialize the lock."""
        self.hass = hass
        self._nuki_lock = nuki_lock
        self._locked = nuki_lock.is_locked
        self._name = nuki_lock.name
        self._battery_critical = nuki_lock.battery_critical

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Callback when entity is added to hass."""
        if not DOMAIN in self.hass.data:
            self.hass.data[DOMAIN] = {}
        if not 'lock' in self.hass.data[DOMAIN]:
            self.hass.data[DOMAIN]['lock'] = []
        self.hass.data[DOMAIN]['lock'].append(self)

    @property
    def name(self):
        """Return the name of the lock."""
        return self._name

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return self._locked

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        data = {
            ATTR_BATTERY_CRITICAL: self._battery_critical,
            ATTR_NUKI_ID: self._nuki_lock.nuki_id}
        return data

    @Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update(self):
        """Update the nuki lock properties."""
        self._nuki_lock.update(aggressive=False)
        self._name = self._nuki_lock.name
        self._locked = self._nuki_lock.is_locked
        self._battery_critical = self._nuki_lock.battery_critical

    def lock(self, **kwargs):
        """Lock the device."""
        self._nuki_lock.lock()

    def unlock(self, **kwargs):
        """Unlock the device."""
        self._nuki_lock.unlock()

    def lock_n_go(self, **kwargs):
        """Lock and go.

        This will first unlock the door, then wait for 20 seconds (or another
        amount of time depending on the lock settings) and relock.
        """
        self._nuki_lock.lock_n_go(kwargs)
