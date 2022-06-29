"""Nuki.io lock platform."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pynuki import NukiLock, NukiOpener
from pynuki.constants import MODE_OPENER_CONTINUOUS
import voluptuous as vol

from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NukiEntity
from .const import (
    ATTR_BATTERY_CRITICAL,
    ATTR_ENABLE,
    ATTR_NUKI_ID,
    ATTR_UNLATCH,
    DATA_COORDINATOR,
    DATA_LOCKS,
    DATA_OPENERS,
    DOMAIN as NUKI_DOMAIN,
    ERROR_STATES,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Nuki lock platform."""
    data = hass.data[NUKI_DOMAIN][entry.entry_id]
    coordinator = data[DATA_COORDINATOR]

    entities: list[NukiDeviceEntity] = [
        NukiLockEntity(coordinator, lock) for lock in data[DATA_LOCKS]
    ]
    entities.extend(
        [NukiOpenerEntity(coordinator, opener) for opener in data[DATA_OPENERS]]
    )
    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "lock_n_go",
        {
            vol.Optional(ATTR_UNLATCH, default=False): cv.boolean,
        },
        "lock_n_go",
    )

    platform.async_register_entity_service(
        "set_continuous_mode",
        {
            vol.Required(ATTR_ENABLE): cv.boolean,
        },
        "set_continuous_mode",
    )


class NukiDeviceEntity(NukiEntity, LockEntity, ABC):
    """Representation of a Nuki device."""

    _attr_supported_features = LockEntityFeature.OPEN

    @property
    def name(self) -> str | None:
        """Return the name of the lock."""
        return self._nuki_device.name

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return self._nuki_device.nuki_id

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device specific state attributes."""
        return {
            ATTR_BATTERY_CRITICAL: self._nuki_device.battery_critical,
            ATTR_NUKI_ID: self._nuki_device.nuki_id,
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._nuki_device.state not in ERROR_STATES

    @abstractmethod
    def lock(self, **kwargs: Any) -> None:
        """Lock the device."""

    @abstractmethod
    def unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""

    @abstractmethod
    def open(self, **kwargs: Any) -> None:
        """Open the door latch."""


class NukiLockEntity(NukiDeviceEntity):
    """Representation of a Nuki lock."""

    _nuki_device: NukiLock

    @property
    def is_locked(self) -> bool:
        """Return true if lock is locked."""
        return self._nuki_device.is_locked

    def lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        self._nuki_device.lock()

    def unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        self._nuki_device.unlock()

    def open(self, **kwargs: Any) -> None:
        """Open the door latch."""
        self._nuki_device.unlatch()

    def lock_n_go(self, unlatch: bool) -> None:
        """Lock and go.

        This will first unlock the door, then wait for 20 seconds (or another
        amount of time depending on the lock settings) and relock.
        """
        self._nuki_device.lock_n_go(unlatch)


class NukiOpenerEntity(NukiDeviceEntity):
    """Representation of a Nuki opener."""

    _nuki_device: NukiOpener

    @property
    def is_locked(self) -> bool:
        """Return true if either ring-to-open or continuous mode is enabled."""
        return not (
            self._nuki_device.is_rto_activated
            or self._nuki_device.mode == MODE_OPENER_CONTINUOUS
        )

    def lock(self, **kwargs: Any) -> None:
        """Disable ring-to-open."""
        self._nuki_device.deactivate_rto()

    def unlock(self, **kwargs: Any) -> None:
        """Enable ring-to-open."""
        self._nuki_device.activate_rto()

    def open(self, **kwargs: Any) -> None:
        """Buzz open the door."""
        self._nuki_device.electric_strike_actuation()

    def lock_n_go(self, unlatch: bool) -> None:
        """Stub service."""

    def set_continuous_mode(self, enable: bool) -> None:
        """Continuous Mode.

        This feature will cause the door to automatically open when anyone
        rings the bell. This is similar to ring-to-open, except that it does
        not automatically deactivate
        """
        if enable:
            self._nuki_device.activate_continuous_mode()
        else:
            self._nuki_device.deactivate_continuous_mode()
