"""Component to interface with locks that can be controlled remotely."""
from datetime import timedelta
import functools as ft
import logging
from typing import final

import voluptuous as vol

from homeassistant.const import (
    ATTR_CODE,
    ATTR_CODE_FORMAT,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
    STATE_LOCKED,
    STATE_UNLOCKED,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
    make_entity_service_schema,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)

ATTR_CHANGED_BY = "changed_by"

DOMAIN = "lock"
SCAN_INTERVAL = timedelta(seconds=30)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

LOCK_SERVICE_SCHEMA = make_entity_service_schema({vol.Optional(ATTR_CODE): cv.string})

# Bitfield of features supported by the lock entity
SUPPORT_OPEN = 1

PROP_TO_ATTR = {"changed_by": ATTR_CHANGED_BY, "code_format": ATTR_CODE_FORMAT}


async def async_setup(hass, config):
    """Track states and offer events for locks."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_UNLOCK, LOCK_SERVICE_SCHEMA, "async_unlock"
    )
    component.async_register_entity_service(
        SERVICE_LOCK, LOCK_SERVICE_SCHEMA, "async_lock"
    )
    component.async_register_entity_service(
        SERVICE_OPEN, LOCK_SERVICE_SCHEMA, "async_open"
    )

    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class LockEntity(Entity):
    """Base class for lock entities."""

    @property
    def changed_by(self):
        """Last change triggered by."""
        return None

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

    async def async_lock(self, **kwargs):
        """Lock the lock."""
        await self.hass.async_add_executor_job(ft.partial(self.lock, **kwargs))

    def unlock(self, **kwargs):
        """Unlock the lock."""
        raise NotImplementedError()

    async def async_unlock(self, **kwargs):
        """Unlock the lock."""
        await self.hass.async_add_executor_job(ft.partial(self.unlock, **kwargs))

    def open(self, **kwargs):
        """Open the door latch."""
        raise NotImplementedError()

    async def async_open(self, **kwargs):
        """Open the door latch."""
        await self.hass.async_add_executor_job(ft.partial(self.open, **kwargs))

    @final
    @property
    def state_attributes(self):
        """Return the state attributes."""
        state_attr = {}
        for prop, attr in PROP_TO_ATTR.items():
            value = getattr(self, prop)
            if value is not None:
                state_attr[attr] = value
        return state_attr

    @property
    def state(self):
        """Return the state."""
        locked = self.is_locked
        if locked is None:
            return None
        return STATE_LOCKED if locked else STATE_UNLOCKED


class LockDevice(LockEntity):
    """Representation of a lock (for backwards compatibility)."""

    def __init_subclass__(cls, **kwargs):
        """Print deprecation warning."""
        super().__init_subclass__(**kwargs)
        _LOGGER.warning(
            "LockDevice is deprecated, modify %s to extend LockEntity",
            cls.__name__,
        )
