"""Nuki.io lock platform."""
from abc import ABC, abstractmethod
import logging

from pynuki import MODE_OPENER_CONTINUOUS
import voluptuous as vol

from homeassistant.components.lock import PLATFORM_SCHEMA, SUPPORT_OPEN, LockEntity
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.helpers import config_validation as cv, entity_platform

from . import NukiEntity
from .const import (
    ATTR_BATTERY_CRITICAL,
    ATTR_ENABLE,
    ATTR_NUKI_ID,
    ATTR_UNLATCH,
    DATA_COORDINATOR,
    DATA_LOCKS,
    DATA_OPENERS,
    DEFAULT_PORT,
    DOMAIN as NUKI_DOMAIN,
    ERROR_STATES,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_TOKEN): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Nuki lock platform."""
    _LOGGER.warning(
        "Loading Nuki by lock platform configuration is deprecated and will be removed in the future"
    )


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Nuki lock platform."""
    data = hass.data[NUKI_DOMAIN][entry.entry_id]
    coordinator = data[DATA_COORDINATOR]

    entities = [NukiLockEntity(coordinator, lock) for lock in data[DATA_LOCKS]]
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

    @property
    def name(self):
        """Return the name of the lock."""
        return self._nuki_device.name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._nuki_device.nuki_id

    @property
    @abstractmethod
    def is_locked(self):
        """Return true if lock is locked."""

    @property
    def extra_state_attributes(self):
        """Return the device specific state attributes."""
        data = {
            ATTR_BATTERY_CRITICAL: self._nuki_device.battery_critical,
            ATTR_NUKI_ID: self._nuki_device.nuki_id,
        }
        return data

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._nuki_device.state not in ERROR_STATES

    @abstractmethod
    def lock(self, **kwargs):
        """Lock the device."""

    @abstractmethod
    def unlock(self, **kwargs):
        """Unlock the device."""

    @abstractmethod
    def open(self, **kwargs):
        """Open the door latch."""


class NukiLockEntity(NukiDeviceEntity):
    """Representation of a Nuki lock."""

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return self._nuki_device.is_locked

    def lock(self, **kwargs):
        """Lock the device."""
        self._nuki_device.lock()

    def unlock(self, **kwargs):
        """Unlock the device."""
        self._nuki_device.unlock()

    def open(self, **kwargs):
        """Open the door latch."""
        self._nuki_device.unlatch()

    def lock_n_go(self, unlatch):
        """Lock and go.

        This will first unlock the door, then wait for 20 seconds (or another
        amount of time depending on the lock settings) and relock.
        """
        self._nuki_device.lock_n_go(unlatch)


class NukiOpenerEntity(NukiDeviceEntity):
    """Representation of a Nuki opener."""

    @property
    def is_locked(self):
        """Return true if either ring-to-open or continuous mode is enabled."""
        return not (
            self._nuki_device.is_rto_activated
            or self._nuki_device.mode == MODE_OPENER_CONTINUOUS
        )

    def lock(self, **kwargs):
        """Disable ring-to-open."""
        self._nuki_device.deactivate_rto()

    def unlock(self, **kwargs):
        """Enable ring-to-open."""
        self._nuki_device.activate_rto()

    def open(self, **kwargs):
        """Buzz open the door."""
        self._nuki_device.electric_strike_actuation()

    def lock_n_go(self, unlatch):
        """Stub service."""

    def set_continuous_mode(self, enable):
        """Continuous Mode.

        This feature will cause the door to automatically open when anyone
        rings the bell. This is similar to ring-to-open, except that it does
        not automatically deactivate
        """
        if enable:
            self._nuki_device.activate_continuous_mode()
        else:
            self._nuki_device.deactivate_continuous_mode()
