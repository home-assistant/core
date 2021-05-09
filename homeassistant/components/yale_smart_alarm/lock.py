"""Support for Yale Lock"""
from __future__ import annotations

import asyncio
import logging

import voluptuous as vol
from yalesmartalarmclient.client import AuthenticationError, YaleSmartAlarmClient

from homeassistant.components.lock import PLATFORM_SCHEMA, LockEntity
from homeassistant.const import (
    ATTR_CODE,
    CONF_CODE,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_LOCKED,
    STATE_UNAVAILABLE,
    STATE_UNLOCKED,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_AREA_ID, DEFAULT_AREA_ID, DEFAULT_NAME, DOMAIN, LOGGER
from .coordinator import YaleDataUpdateCoordinator


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the lock platform"""

    return True


async def async_setup_entry(hass, entry, async_add_entities):
    """ Set up the lock entry """
    coordinator: YaleDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    async_add_entities(
        YaleDoorlock(coordinator, key) for key in coordinator.data["lock"]
    )

    return True


class YaleDoorlock(CoordinatorEntity, LockEntity):
    """Representation of a Yale doorlock."""

    def __init__(self, coordinator: YaleDataUpdateCoordinator, name: str):
        """Initialize the Yale Alarm Device."""
        self._name = name
        self._state = STATE_UNAVAILABLE
        self.coordinator = coordinator
        super().__init__(coordinator)

        self._state_map = {
            "locked": STATE_LOCKED,
            "unlocked": STATE_UNLOCKED,
            "dooropen": STATE_UNLOCKED,
            "unknown": STATE_UNAVAILABLE,
        }

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state_map.get(self.coordinator.data["lock"][self._name])

    @property
    def is_locked(self):
        return (
            self._state_map.get(self.coordinator.data["lock"][self._name])
            == STATE_LOCKED
        )

    @property
    def code_format(self) -> str:
        """Return the required six digit code."""
        return "^\\d{6}$"

    async def async_unlock(self, **kwargs) -> None:
        """Send unlock command."""
        code = kwargs.get(ATTR_CODE, self.coordinator._entry.data.get(CONF_CODE))
        if code is None:
            LOGGER.error("Code required but none provided")
            return

        await self.async_set_lock_state(code, "unlock")

    async def async_lock(self, **kwargs) -> None:
        """Send lock command."""
        code = None
        await self.async_set_lock_state(code, "lock")

    async def async_set_lock_state(self, code: str, state: str) -> None:
        """Send set lock state command."""
        get_lock = await self.hass.async_add_executor_job(
            self.coordinator._yale.lock_api.get, self._name
        )
        if state == "lock":

            lock_state = await self.hass.async_add_executor_job(
                self.coordinator._yale.lock_api.close_lock,
                get_lock,
            )
            expected = 1
        elif state == "unlock":
            lock_state = await self.hass.async_add_executor_job(
                self.coordinator._yale.lock_api.open_lock,
                get_lock,
                code,
            )
            expected = 2

        LOGGER.debug("Yale doorlock %s", state)
        transaction = None
        attempts = 0
        while lock_state != True and transaction != expected:
            transaction = await self.hass.async_add_executor_job(
                self.coordinator._yale.lock_api.get(self._name).state._value_
            )
            attempts += 1
            if attempts == 30:
                break
            if attempts > 1:
                await asyncio.sleep(0.5)
        if state == transaction:
            self._state = state