"""
Component to interface with various locks that can be controlled remotely.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/lock/
"""
import asyncio
from datetime import timedelta
import functools as ft
import logging
import os

import voluptuous as vol

from homeassistant.config import load_yaml_config_file
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    ATTR_CODE, ATTR_CODE_FORMAT, ATTR_ENTITY_ID, STATE_LOCKED, STATE_UNLOCKED,
    STATE_UNKNOWN, SERVICE_LOCK, SERVICE_UNLOCK)
from homeassistant.components import group

ATTR_CHANGED_BY = 'changed_by'

DOMAIN = 'lock'

ENTITY_ID_ALL_LOCKS = group.ENTITY_ID_FORMAT.format('all_locks')
ENTITY_ID_FORMAT = DOMAIN + '.{}'

GROUP_NAME_ALL_LOCKS = 'all locks'

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

SCAN_INTERVAL = timedelta(seconds=30)

LOCK_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_CODE): cv.string,
})

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


@asyncio.coroutine
def async_setup(hass, config):
    """Track states and offer events for locks."""
    component = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, GROUP_NAME_ALL_LOCKS)

    yield from component.async_setup(config)

    @asyncio.coroutine
    def async_handle_lock_service(service):
        """Handle calls to the lock services."""
        target_locks = component.async_extract_from_service(service)

        code = service.data.get(ATTR_CODE)

        for entity in target_locks:
            if service.service == SERVICE_LOCK:
                yield from entity.async_lock(code=code)
            else:
                yield from entity.async_unlock(code=code)

        update_tasks = []

        for entity in target_locks:
            if not entity.should_poll:
                continue

            update_coro = hass.async_add_job(
                entity.async_update_ha_state(True))
            if hasattr(entity, 'async_update'):
                update_tasks.append(update_coro)
            else:
                yield from update_coro

        if update_tasks:
            yield from asyncio.wait(update_tasks, loop=hass.loop)

    descriptions = yield from hass.async_add_job(
        load_yaml_config_file, os.path.join(
            os.path.dirname(__file__), 'services.yaml'))

    hass.services.async_register(
        DOMAIN, SERVICE_UNLOCK, async_handle_lock_service,
        descriptions.get(SERVICE_UNLOCK), schema=LOCK_SERVICE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_LOCK, async_handle_lock_service,
        descriptions.get(SERVICE_LOCK), schema=LOCK_SERVICE_SCHEMA)

    return True


class LockDevice(Entity):
    """Representation of a lock."""

    @property
    def changed_by(self):
        """Last change triggered by."""
        return None

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

    def async_lock(self, **kwargs):
        """Lock the lock.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(ft.partial(self.lock, **kwargs))

    def unlock(self, **kwargs):
        """Unlock the lock."""
        raise NotImplementedError()

    def async_unlock(self, **kwargs):
        """Unlock the lock.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(ft.partial(self.unlock, **kwargs))

    @property
    def state_attributes(self):
        """Return the state attributes."""
        if self.code_format is None:
            return None
        state_attr = {
            ATTR_CODE_FORMAT: self.code_format,
            ATTR_CHANGED_BY: self.changed_by
        }
        return state_attr

    @property
    def state(self):
        """Return the state."""
        locked = self.is_locked
        if locked is None:
            return STATE_UNKNOWN
        return STATE_LOCKED if locked else STATE_UNLOCKED
