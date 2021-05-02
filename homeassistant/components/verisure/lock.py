"""Support for Verisure locks."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Callable

from verisure import Error as VerisureError

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_CODE, STATE_LOCKED, STATE_UNLOCKED
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.entity_platform import current_platform
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_GIID,
    CONF_LOCK_CODE_DIGITS,
    CONF_LOCK_DEFAULT_CODE,
    DEFAULT_LOCK_CODE_DIGITS,
    DOMAIN,
    LOGGER,
    SERVICE_DISABLE_AUTOLOCK,
    SERVICE_ENABLE_AUTOLOCK,
)
from .coordinator import VerisureDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[Iterable[Entity]], None],
) -> None:
    """Set up Verisure alarm control panel from a config entry."""
    coordinator: VerisureDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    platform = current_platform.get()
    platform.async_register_entity_service(
        SERVICE_DISABLE_AUTOLOCK,
        {},
        VerisureDoorlock.disable_autolock.__name__,
    )
    platform.async_register_entity_service(
        SERVICE_ENABLE_AUTOLOCK,
        {},
        VerisureDoorlock.enable_autolock.__name__,
    )

    async_add_entities(
        VerisureDoorlock(coordinator, serial_number)
        for serial_number in coordinator.data["locks"]
    )


class VerisureDoorlock(CoordinatorEntity, LockEntity):
    """Representation of a Verisure doorlock."""

    coordinator: VerisureDataUpdateCoordinator

    def __init__(
        self, coordinator: VerisureDataUpdateCoordinator, serial_number: str
    ) -> None:
        """Initialize the Verisure lock."""
        super().__init__(coordinator)
        self.serial_number = serial_number
        self._state = None
        self._digits = coordinator.entry.options.get(
            CONF_LOCK_CODE_DIGITS, DEFAULT_LOCK_CODE_DIGITS
        )

    @property
    def name(self) -> str:
        """Return the name of this entity."""
        return self.coordinator.data["locks"][self.serial_number]["area"]

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return self.serial_number

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        area = self.coordinator.data["locks"][self.serial_number]["area"]
        return {
            "name": area,
            "suggested_area": area,
            "manufacturer": "Verisure",
            "model": "Lockguard Smartlock",
            "identifiers": {(DOMAIN, self.serial_number)},
            "via_device": (DOMAIN, self.coordinator.entry.data[CONF_GIID]),
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available and self.serial_number in self.coordinator.data["locks"]
        )

    @property
    def changed_by(self) -> str | None:
        """Last change triggered by."""
        return self.coordinator.data["locks"][self.serial_number].get("userString")

    @property
    def code_format(self) -> str:
        """Return the required six digit code."""
        return "^\\d{%s}$" % self._digits

    @property
    def is_locked(self) -> bool:
        """Return true if lock is locked."""
        return (
            self.coordinator.data["locks"][self.serial_number]["lockedState"]
            == "LOCKED"
        )

    async def async_unlock(self, **kwargs) -> None:
        """Send unlock command."""
        code = kwargs.get(
            ATTR_CODE, self.coordinator.entry.options.get(CONF_LOCK_DEFAULT_CODE)
        )
        if code is None:
            LOGGER.error("Code required but none provided")
            return

        await self.async_set_lock_state(code, STATE_UNLOCKED)

    async def async_lock(self, **kwargs) -> None:
        """Send lock command."""
        code = kwargs.get(
            ATTR_CODE, self.coordinator.entry.options.get(CONF_LOCK_DEFAULT_CODE)
        )
        if code is None:
            LOGGER.error("Code required but none provided")
            return

        await self.async_set_lock_state(code, STATE_LOCKED)

    async def async_set_lock_state(self, code: str, state: str) -> None:
        """Send set lock state command."""
        target_state = "lock" if state == STATE_LOCKED else "unlock"
        lock_state = await self.hass.async_add_executor_job(
            self.coordinator.verisure.set_lock_state,
            code,
            self.serial_number,
            target_state,
        )

        LOGGER.debug("Verisure doorlock %s", state)
        transaction = {}
        attempts = 0
        while "result" not in transaction:
            transaction = await self.hass.async_add_executor_job(
                self.coordinator.verisure.get_lock_state_transaction,
                lock_state["doorLockStateChangeTransactionId"],
            )
            attempts += 1
            if attempts == 30:
                break
            if attempts > 1:
                await asyncio.sleep(0.5)
        if transaction["result"] == "OK":
            self._state = state

    def disable_autolock(self) -> None:
        """Disable autolock on a doorlock."""
        try:
            self.coordinator.verisure.set_lock_config(
                self.serial_number, auto_lock_enabled=False
            )
            LOGGER.debug("Disabling autolock on %s", self.serial_number)
        except VerisureError as ex:
            LOGGER.error("Could not disable autolock, %s", ex)

    def enable_autolock(self) -> None:
        """Enable autolock on a doorlock."""
        try:
            self.coordinator.verisure.set_lock_config(
                self.serial_number, auto_lock_enabled=True
            )
            LOGGER.debug("Enabling autolock on %s", self.serial_number)
        except VerisureError as ex:
            LOGGER.error("Could not enable autolock, %s", ex)
