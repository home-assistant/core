"""Component to interface with locks that can be controlled remotely."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import IntFlag
import functools as ft
import logging
import re
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
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
    make_entity_service_schema,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.service import remove_entity_service_fields
from homeassistant.helpers.typing import ConfigType, StateType

_LOGGER = logging.getLogger(__name__)

ATTR_CHANGED_BY = "changed_by"

DOMAIN = "lock"
SCAN_INTERVAL = timedelta(seconds=30)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

LOCK_SERVICE_SCHEMA = make_entity_service_schema({vol.Optional(ATTR_CODE): cv.string})


class LockEntityFeature(IntFlag):
    """Supported features of the lock entity."""

    OPEN = 1


# The SUPPORT_OPEN constant is deprecated as of Home Assistant 2022.5.
# Please use the LockEntityFeature enum instead.
SUPPORT_OPEN = 1

PROP_TO_ATTR = {"changed_by": ATTR_CHANGED_BY, "code_format": ATTR_CODE_FORMAT}

# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Track states and offer events for locks."""
    component = hass.data[DOMAIN] = EntityComponent[LockEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_UNLOCK, LOCK_SERVICE_SCHEMA, _async_unlock
    )
    component.async_register_entity_service(
        SERVICE_LOCK, LOCK_SERVICE_SCHEMA, _async_lock
    )
    component.async_register_entity_service(
        SERVICE_OPEN, LOCK_SERVICE_SCHEMA, _async_open, [LockEntityFeature.OPEN]
    )

    return True


async def _async_lock(entity: LockEntity, service_call: ServiceCall) -> None:
    """Lock the lock."""
    code: str = service_call.data.get(ATTR_CODE, "")
    if entity.code_format_cmp and not entity.code_format_cmp.match(code):
        raise ValueError(
            f"Code '{code}' for locking {entity.entity_id} doesn't match pattern {entity.code_format}"
        )
    await entity.async_lock(**remove_entity_service_fields(service_call))


async def _async_unlock(entity: LockEntity, service_call: ServiceCall) -> None:
    """Unlock the lock."""
    code: str = service_call.data.get(ATTR_CODE, "")
    if entity.code_format_cmp and not entity.code_format_cmp.match(code):
        raise ValueError(
            f"Code '{code}' for unlocking {entity.entity_id} doesn't match pattern {entity.code_format}"
        )
    await entity.async_unlock(**remove_entity_service_fields(service_call))


async def _async_open(entity: LockEntity, service_call: ServiceCall) -> None:
    """Open the door latch."""
    code: str = service_call.data.get(ATTR_CODE, "")
    if entity.code_format_cmp and not entity.code_format_cmp.match(code):
        raise ValueError(
            f"Code '{code}' for opening {entity.entity_id} doesn't match pattern {entity.code_format}"
        )
    await entity.async_open(**remove_entity_service_fields(service_call))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[LockEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[LockEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


@dataclass
class LockEntityDescription(EntityDescription):
    """A class that describes lock entities."""


class LockEntity(Entity):
    """Base class for lock entities."""

    entity_description: LockEntityDescription
    _attr_changed_by: str | None = None
    _attr_code_format: str | None = None
    _attr_is_locked: bool | None = None
    _attr_is_locking: bool | None = None
    _attr_is_unlocking: bool | None = None
    _attr_is_jammed: bool | None = None
    _attr_state: None = None
    _attr_supported_features: LockEntityFeature = LockEntityFeature(0)
    __code_format_cmp: re.Pattern[str] | None = None

    @property
    def changed_by(self) -> str | None:
        """Last change triggered by."""
        return self._attr_changed_by

    @property
    def code_format(self) -> str | None:
        """Regex for code format or None if no code is required."""
        return self._attr_code_format

    @property
    @final
    def code_format_cmp(self) -> re.Pattern[str] | None:
        """Return a compiled code_format."""
        if self.code_format is None:
            self.__code_format_cmp = None
            return None
        if (
            not self.__code_format_cmp
            or self.code_format != self.__code_format_cmp.pattern
        ):
            self.__code_format_cmp = re.compile(self.code_format)
        return self.__code_format_cmp

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
            if (value := getattr(self, prop)) is not None:
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
        if (locked := self.is_locked) is None:
            return None
        return STATE_LOCKED if locked else STATE_UNLOCKED

    @property
    def supported_features(self) -> LockEntityFeature:
        """Return the list of supported features."""
        return self._attr_supported_features
