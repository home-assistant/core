"""Nuki.io lock platform."""

from abc import ABC, abstractmethod
import logging

import voluptuous as vol

from homeassistant.components.lock import SUPPORT_OPEN, LockEntity
from homeassistant.const import ATTR_ENTITY_ID
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.service import extract_entity_ids

from . import NukiEntity
from .const import (
    ATTR_BATTERY_CRITICAL,
    ATTR_NUKI_ID,
    ATTR_UNLATCH,
    DATA_COORDINATOR,
    DATA_LOCKS,
    DATA_OPENERS,
    DOMAIN,
    ERROR_STATES,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_LOCK_N_GO = "lock_n_go"
LOCK_N_GO_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Optional(ATTR_UNLATCH, default=False): cv.boolean,
    }
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Nuki lock platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data[DATA_COORDINATOR]

    entities = [
        NukiLockEntity(coordinator, lock)
        for lock in hass.data[DOMAIN][entry.entry_id][DATA_LOCKS]
    ]

    def service_handler(service):
        """Service handler for nuki services."""
        entity_ids = extract_entity_ids(hass, service)
        unlatch = service.data[ATTR_UNLATCH]

        for lock in entities:
            if lock.entity_id not in entity_ids:
                continue
            lock.lock_n_go(unlatch=unlatch)

    hass.services.async_register(
        DOMAIN,
        SERVICE_LOCK_N_GO,
        service_handler,
        schema=LOCK_N_GO_SERVICE_SCHEMA,
    )

    entities.extend(
        [
            NukiOpenerEntity(coordinator, opener)
            for opener in hass.data[DOMAIN][entry.entry_id][DATA_OPENERS]
        ]
    )

    async_add_entities(entities)


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
    def device_state_attributes(self):
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
        return self._nuki_device.state not in ERROR_STATES

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

    @property
    def is_door_sensor_activated(self):
        """Return true if door sensor is present and activated."""
        return self._nuki_device.is_door_sensor_activated

    def lock(self, **kwargs):
        """Lock the device."""
        self._nuki_device.lock()

    def unlock(self, **kwargs):
        """Unlock the device."""
        self._nuki_device.unlock()

    def open(self, **kwargs):
        """Open the door latch."""
        self._nuki_device.unlatch()

    def lock_n_go(self, unlatch=False, **kwargs):
        """Lock and go.

        This will first unlock the door, then wait for 20 seconds (or another
        amount of time depending on the lock settings) and relock.
        """
        self._nuki_device.lock_n_go(unlatch, kwargs)


class NukiOpenerEntity(NukiDeviceEntity):
    """Representation of a Nuki opener."""

    @property
    def is_locked(self):
        """Return true if ring-to-open is enabled."""
        return not self._nuki_device.is_rto_activated

    def lock(self, **kwargs):
        """Disable ring-to-open."""
        self._nuki_device.deactivate_rto()

    def unlock(self, **kwargs):
        """Enable ring-to-open."""
        self._nuki_device.activate_rto()

    def open(self, **kwargs):
        """Buzz open the door."""
        self._nuki_device.electric_strike_actuation()
