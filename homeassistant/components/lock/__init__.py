"""Component to interface with locks that can be controlled remotely."""

from __future__ import annotations

from datetime import timedelta
from enum import IntFlag
import functools as ft
from functools import cached_property
import logging
import re
from typing import TYPE_CHECKING, Any, final

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (  # noqa: F401
    _DEPRECATED_STATE_JAMMED,
    _DEPRECATED_STATE_LOCKED,
    _DEPRECATED_STATE_LOCKING,
    _DEPRECATED_STATE_UNLOCKED,
    _DEPRECATED_STATE_UNLOCKING,
    ATTR_CODE,
    ATTR_CODE_FORMAT,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.deprecation import (
    DeprecatedConstantEnum,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType, StateType
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, LockState

_LOGGER = logging.getLogger(__name__)

DATA_COMPONENT: HassKey[EntityComponent[LockEntity]] = HassKey(DOMAIN)
ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=30)

ATTR_CHANGED_BY = "changed_by"
CONF_DEFAULT_CODE = "default_code"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

LOCK_SERVICE_SCHEMA = cv.make_entity_service_schema(
    {vol.Optional(ATTR_CODE): cv.string}
)


class LockEntityFeature(IntFlag):
    """Supported features of the lock entity."""

    OPEN = 1


# The SUPPORT_OPEN constant is deprecated as of Home Assistant 2022.5.
# Please use the LockEntityFeature enum instead.
_DEPRECATED_SUPPORT_OPEN = DeprecatedConstantEnum(LockEntityFeature.OPEN, "2025.1")

PROP_TO_ATTR = {"changed_by": ATTR_CHANGED_BY, "code_format": ATTR_CODE_FORMAT}

# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Track states and offer events for locks."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[LockEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_UNLOCK, LOCK_SERVICE_SCHEMA, "async_handle_unlock_service"
    )
    component.async_register_entity_service(
        SERVICE_LOCK, LOCK_SERVICE_SCHEMA, "async_handle_lock_service"
    )
    component.async_register_entity_service(
        SERVICE_OPEN,
        LOCK_SERVICE_SCHEMA,
        "async_handle_open_service",
        [LockEntityFeature.OPEN],
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


class LockEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes lock entities."""


CACHED_PROPERTIES_WITH_ATTR_ = {
    "changed_by",
    "code_format",
    "is_locked",
    "is_locking",
    "is_unlocking",
    "is_open",
    "is_opening",
    "is_jammed",
    "supported_features",
}


class LockEntity(Entity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Base class for lock entities."""

    entity_description: LockEntityDescription
    _attr_changed_by: str | None = None
    _attr_code_format: str | None = None
    _attr_is_locked: bool | None = None
    _attr_is_locking: bool | None = None
    _attr_is_open: bool | None = None
    _attr_is_opening: bool | None = None
    _attr_is_unlocking: bool | None = None
    _attr_is_jammed: bool | None = None
    _attr_state: None = None
    _attr_supported_features: LockEntityFeature = LockEntityFeature(0)
    _lock_option_default_code: str = ""
    __code_format_cmp: re.Pattern[str] | None = None

    @final
    @callback
    def add_default_code(self, data: dict[Any, Any]) -> dict[Any, Any]:
        """Add default lock code."""
        code: str = data.pop(ATTR_CODE, "")
        if not code:
            code = self._lock_option_default_code
        if self.code_format_cmp and not self.code_format_cmp.match(code):
            if TYPE_CHECKING:
                assert self.code_format
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="add_default_code",
                translation_placeholders={
                    "entity_id": self.entity_id,
                    "code_format": self.code_format,
                },
            )
        if code:
            data[ATTR_CODE] = code
        return data

    @cached_property
    def changed_by(self) -> str | None:
        """Last change triggered by."""
        return self._attr_changed_by

    @cached_property
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

    @cached_property
    def is_locked(self) -> bool | None:
        """Return true if the lock is locked."""
        return self._attr_is_locked

    @cached_property
    def is_locking(self) -> bool | None:
        """Return true if the lock is locking."""
        return self._attr_is_locking

    @cached_property
    def is_unlocking(self) -> bool | None:
        """Return true if the lock is unlocking."""
        return self._attr_is_unlocking

    @cached_property
    def is_open(self) -> bool | None:
        """Return true if the lock is open."""
        return self._attr_is_open

    @cached_property
    def is_opening(self) -> bool | None:
        """Return true if the lock is opening."""
        return self._attr_is_opening

    @cached_property
    def is_jammed(self) -> bool | None:
        """Return true if the lock is jammed (incomplete locking)."""
        return self._attr_is_jammed

    @final
    async def async_handle_lock_service(self, **kwargs: Any) -> None:
        """Add default code and lock."""
        await self.async_lock(**self.add_default_code(kwargs))

    def lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        raise NotImplementedError

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        await self.hass.async_add_executor_job(ft.partial(self.lock, **kwargs))

    @final
    async def async_handle_unlock_service(self, **kwargs: Any) -> None:
        """Add default code and unlock."""
        await self.async_unlock(**self.add_default_code(kwargs))

    def unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        raise NotImplementedError

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        await self.hass.async_add_executor_job(ft.partial(self.unlock, **kwargs))

    @final
    async def async_handle_open_service(self, **kwargs: Any) -> None:
        """Add default code and open."""
        await self.async_open(**self.add_default_code(kwargs))

    def open(self, **kwargs: Any) -> None:
        """Open the door latch."""
        raise NotImplementedError

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
            return LockState.JAMMED
        if self.is_opening:
            return LockState.OPENING
        if self.is_locking:
            return LockState.LOCKING
        if self.is_open:
            return LockState.OPEN
        if self.is_unlocking:
            return LockState.UNLOCKING
        if (locked := self.is_locked) is None:
            return None
        return LockState.LOCKED if locked else LockState.UNLOCKED

    @cached_property
    def supported_features(self) -> LockEntityFeature:
        """Return the list of supported features."""
        features = self._attr_supported_features
        if type(features) is int:  # noqa: E721
            new_features = LockEntityFeature(features)
            self._report_deprecated_supported_features_values(new_features)
            return new_features
        return features

    async def async_internal_added_to_hass(self) -> None:
        """Call when the sensor entity is added to hass."""
        await super().async_internal_added_to_hass()
        if not self.registry_entry:
            return
        self._async_read_entity_options()

    @callback
    def async_registry_entry_updated(self) -> None:
        """Run when the entity registry entry has been updated."""
        self._async_read_entity_options()

    @callback
    def _async_read_entity_options(self) -> None:
        """Read entity options from entity registry.

        Called when the entity registry entry has been updated and before the lock is
        added to the state machine.
        """
        assert self.registry_entry
        if (lock_options := self.registry_entry.options.get(DOMAIN)) and (
            custom_default_lock_code := lock_options.get(CONF_DEFAULT_CODE)
        ):
            if self.code_format_cmp and self.code_format_cmp.match(
                custom_default_lock_code
            ):
                self._lock_option_default_code = custom_default_lock_code
            return

        self._lock_option_default_code = ""


# These can be removed if no deprecated constant are in this module anymore
__getattr__ = ft.partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = ft.partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
