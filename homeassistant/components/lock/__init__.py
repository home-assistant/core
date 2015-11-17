"""
homeassistant.components.lock
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Component to interface with various locks that can be controlled remotely.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/lock/
"""
from datetime import timedelta
import logging
import os

from homeassistant.config import load_yaml_config_file
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import ToggleEntity

from homeassistant.const import (
    STATE_LOCKED, SERVICE_LOCK, SERVICE_UNLOCK, ATTR_ENTITY_ID)
from homeassistant.components import (
    group, wink)

DOMAIN = 'lock'
DEPENDENCIES = []
SCAN_INTERVAL = 30

GROUP_NAME_ALL_LOCKS = 'all locks'
ENTITY_ID_ALL_LOCKS = group.ENTITY_ID_FORMAT.format('all_locks')

ENTITY_ID_FORMAT = DOMAIN + '.{}'

ATTR_LOCKED = "locked"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

# Maps discovered services to their platforms
DISCOVERY_PLATFORMS = {
    wink.DISCOVER_LOCKS: 'wink'
}

PROP_TO_ATTR = {
    'locked': ATTR_LOCKED
}

_LOGGER = logging.getLogger(__name__)


def is_locked(hass, entity_id=None):
    """ Returns if the lock is locked based on the statemachine. """
    entity_id = entity_id or ENTITY_ID_ALL_LOCKS
    return hass.states.is_state(entity_id, STATE_LOCKED)


def do_lock(hass, entity_id=None):
    """ Locks all or specified locks. """
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_LOCK, data)


def do_unlock(hass, entity_id=None):
    """ Unlocks all or specified locks. """
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_UNLOCK, data)


def setup(hass, config):
    """ Track states and offer events for locks. """
    component = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, DISCOVERY_PLATFORMS,
        GROUP_NAME_ALL_LOCKS)
    component.setup(config)

    def handle_lock_service(service):
        """ Handles calls to the lock services. """
        target_locks = component.extract_from_service(service)

        for lock in target_locks:
            if service.service == SERVICE_LOCK:
                lock.do_lock()
            else:
                lock.do_unlock()

            if lock.should_poll:
                lock.update_ha_state(True)

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))
    hass.services.register(DOMAIN, SERVICE_UNLOCK, handle_lock_service,
                           descriptions.get(SERVICE_UNLOCK))
    hass.services.register(DOMAIN, SERVICE_LOCK, handle_lock_service,
                           descriptions.get(SERVICE_LOCK))

    return True


class LockDevice(ToggleEntity):
    """ Represents a lock within Home Assistant. """
    # pylint: disable=no-self-use

    @property
    def locked(self):
        """ Is the lock locked or unlocked. """
        return None

    @property
    def device_state_attributes(self):
        """ Returns device specific state attributes. """
        return None

    @property
    def state_attributes(self):
        """ Returns optional state attributes. """
        data = {}

        for prop, attr in PROP_TO_ATTR.items():
            value = getattr(self, prop)
            if value:
                data[attr] = value

        device_attr = self.device_state_attributes

        if device_attr is not None:
            data.update(device_attr)

        return data
