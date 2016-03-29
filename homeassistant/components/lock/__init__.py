"""
Component to interface with various locks that can be controlled remotely.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/lock/
"""
from datetime import timedelta
import logging
import os

from homeassistant.config import load_yaml_config_file
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import Entity

from homeassistant.const import (
    ATTR_CODE, ATTR_CODE_FORMAT, ATTR_ENTITY_ID, STATE_LOCKED, STATE_UNLOCKED,
    STATE_UNKNOWN, SERVICE_LOCK, SERVICE_UNLOCK)
from homeassistant.components import (group, verisure, wink)

DOMAIN = 'lock'
SCAN_INTERVAL = 30

GROUP_NAME_ALL_LOCKS = 'all locks'
ENTITY_ID_ALL_LOCKS = group.ENTITY_ID_FORMAT.format('all_locks')

ENTITY_ID_FORMAT = DOMAIN + '.{}'

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

# Maps discovered services to their platforms
DISCOVERY_PLATFORMS = {
    wink.DISCOVER_LOCKS: 'wink',
    verisure.DISCOVER_LOCKS: 'verisure'
}

_LOGGER = logging.getLogger(__name__)


def is_locked(hass, entity_id=None):
    """Return if the lock is locked based on the statemachine."""
    entity_id = entity_id or ENTITY_ID_ALL_LOCKS
    return hass.states.is_state(entity_id, STATE_LOCKED)


def lock(hass, entity_id=None, code=None):
    """Lock all or specified locks."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_LOCK, data)


def unlock(hass, entity_id=None, code=None):
    """Unlock all or specified locks."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_UNLOCK, data)


def setup(hass, config):
    """Track states and offer events for locks."""
    component = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, DISCOVERY_PLATFORMS,
        GROUP_NAME_ALL_LOCKS)
    component.setup(config)

    def handle_lock_service(service):
        """Handle calls to the lock services."""
        target_locks = component.extract_from_service(service)

        if ATTR_CODE not in service.data:
            code = None
        else:
            code = service.data[ATTR_CODE]

        for item in target_locks:
            if service.service == SERVICE_LOCK:
                item.lock(code=code)
            else:
                item.unlock(code=code)

            if item.should_poll:
                item.update_ha_state(True)

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))
    hass.services.register(DOMAIN, SERVICE_UNLOCK, handle_lock_service,
                           descriptions.get(SERVICE_UNLOCK))
    hass.services.register(DOMAIN, SERVICE_LOCK, handle_lock_service,
                           descriptions.get(SERVICE_LOCK))

    return True


class LockDevice(Entity):
    """Representation of a lock."""

    # pylint: disable=no-self-use
    @property
    def code_format(self):
        """Regex for code format or None if no code is required."""
        return None

    @property
    def is_locked(self):
        """Return true if the lock is locked."""
        return None

    def lock(self, **kwargs):
        """Lock the lock."""
        raise NotImplementedError()

    def unlock(self, **kwargs):
        """Unlock the lock."""
        raise NotImplementedError()

    @property
    def state_attributes(self):
        """Return the state attributes."""
        if self.code_format is None:
            return None
        state_attr = {
            ATTR_CODE_FORMAT: self.code_format,
        }
        return state_attr

    @property
    def state(self):
        """Return the state."""
        locked = self.is_locked
        if locked is None:
            return STATE_UNKNOWN
        return STATE_LOCKED if locked else STATE_UNLOCKED
