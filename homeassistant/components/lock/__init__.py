"""Component to interface with locks that can be controlled remotely."""
from __future__ import annotations

from datetime import timedelta
import functools as ft
import logging
from typing import Any, final

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_CODE,
    ATTR_CODE_FORMAT,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
    STATE_JAMMED,
    STATE_LOCKED,
    STATE_LOCKING,
    STATE_UNLOCKED,
    STATE_UNLOCKING,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
    make_entity_service_schema,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType, StateType

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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


class LockEntity(Entity):
    """Base class for lock entities."""

    _attr_changed_by: str | None = None
    _attr_code_format: str | None = None
    _attr_is_locked: bool | None = None
    _attr_is_locking: bool | None = None
    _attr_is_unlocking: bool | None = None
    _attr_is_jammed: bool | None = None
    _attr_state: None = None

    @property
    def changed_by(self) -> str | None:
        """Last change triggered by."""
        return self._attr_changed_by

    @property
    def code_format(self) -> str | None:
        """Regex for code format or None if no code is required."""
        return self._attr_code_format

    @property
    def is_locked(self) -> bool | None:
        """Return true if the lock is locked."""
        return self._attr_is_locked

    @property
    def is_locking(self) -> bool | None:
        """Return true if the lock is locking."""
        return self._attr_is_locking

    @property
    def is_unlocking(self) -> bool | None:
        """Return true if the lock is unlocking."""
        return self._attr_is_unlocking

    @property
    def is_jammed(self) -> bool | None:
        """Return true if the lock is jammed (incomplete locking)."""
        return self._attr_is_jammed

    def lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        raise NotImplementedError()

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        await self.hass.async_add_executor_job(ft.partial(self.lock, **kwargs))

    def unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        raise NotImplementedError()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        await self.hass.async_add_executor_job(ft.partial(self.unlock, **kwargs))

    def open(self, **kwargs: Any) -> None:
        """Open the door latch."""
        raise NotImplementedError()

    async def async_open(self, **kwargs: Any) -> None:
        """Open the door latch."""
        await self.hass.async_add_executor_job(ft.partial(self.open, **kwargs))

    @final
    @property
    def state_attributes(self) -> dict[str, StateType]:
        """Return the state attributes."""
        state_attr = {}
        for prop, attr in PROP_TO_ATTR.items():
            value = getattr(self, prop)
            if value is not None:
                state_attr[attr] = value
        return state_attr

    @final
    @property
    def state(self) -> str | None:
        """Return the state."""
        if self.is_jammed:
            return STATE_JAMMED
        if self.is_locking:
            return STATE_LOCKING
        if self.is_unlocking:
            return STATE_UNLOCKING
        locked = self.is_locked
        if locked is None:
            return None
        return STATE_LOCKED if locked else STATE_UNLOCKED


class LockDevice(LockEntity):
    """Representation of a lock (for backwards compatibility)."""

    def __init_subclass__(cls, **kwargs: Any):
        """Print deprecation warning."""
        super().__init_subclass__(**kwargs)  # type: ignore[call-arg]
        _LOGGER.warning(
            "LockDevice is deprecated, modify %s to extend LockEntity",
            cls.__name__,
        )
