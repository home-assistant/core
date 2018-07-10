"""
Nuki.io lock platform.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/lock.nuki/
"""
import asyncio
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.lock import DOMAIN, PLATFORM_SCHEMA, LockDevice
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_HOST, CONF_PORT, CONF_TOKEN)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.service import extract_entity_ids

REQUIREMENTS = ['pynuki==1.3.1']

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 8080

ATTR_BATTERY_CRITICAL = 'battery_critical'
ATTR_NUKI_ID = 'nuki_id'
ATTR_UNLATCH = 'unlatch'

MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=5)
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=30)

NUKI_DATA = 'nuki'

SERVICE_LOCK_N_GO = 'nuki_lock_n_go'
SERVICE_UNLATCH = 'nuki_unlatch'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Required(CONF_TOKEN): cv.string
})

LOCK_N_GO_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_UNLATCH, default=False): cv.boolean
})

UNLATCH_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Nuki lock platform."""
    from pynuki import NukiBridge
    bridge = NukiBridge(config.get(CONF_HOST), config.get(CONF_TOKEN))
    add_devices([NukiLock(lock) for lock in bridge.locks])

    def service_handler(service):
        """Service handler for nuki services."""
        entity_ids = extract_entity_ids(hass, service)
        all_locks = hass.data[NUKI_DATA][DOMAIN]
        target_locks = []
        if not entity_ids:
            target_locks = all_locks
        else:
            for lock in all_locks:
                if lock.entity_id in entity_ids:
                    target_locks.append(lock)
        for lock in target_locks:
            if service.service == SERVICE_LOCK_N_GO:
                unlatch = service.data[ATTR_UNLATCH]
                lock.lock_n_go(unlatch=unlatch)
            elif service.service == SERVICE_UNLATCH:
                lock.unlatch()

    hass.services.register(
        DOMAIN, SERVICE_LOCK_N_GO, service_handler,
        schema=LOCK_N_GO_SERVICE_SCHEMA)
    hass.services.register(
        DOMAIN, SERVICE_UNLATCH, service_handler,
        schema=UNLATCH_SERVICE_SCHEMA)


class NukiLock(LockDevice):
    """Representation of a Nuki lock."""

    def __init__(self, nuki_lock):
        """Initialize the lock."""
        self._nuki_lock = nuki_lock
        self._locked = nuki_lock.is_locked
        self._name = nuki_lock.name
        self._battery_critical = nuki_lock.battery_critical

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Call when entity is added to hass."""
        if NUKI_DATA not in self.hass.data:
            self.hass.data[NUKI_DATA] = {}
        if DOMAIN not in self.hass.data[NUKI_DATA]:
            self.hass.data[NUKI_DATA][DOMAIN] = []
        self.hass.data[NUKI_DATA][DOMAIN].append(self)

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

    def lock_n_go(self, unlatch=False, **kwargs):
        """Lock and go.

        This will first unlock the door, then wait for 20 seconds (or another
        amount of time depending on the lock settings) and relock.
        """
        self._nuki_lock.lock_n_go(unlatch, kwargs)

    def unlatch(self, **kwargs):
        """Unlatch door."""
        self._nuki_lock.unlatch()
