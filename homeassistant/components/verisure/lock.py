"""Support for Verisure locks."""
from __future__ import annotations

import asyncio
from typing import Any

from verisure import Error as VerisureError

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_CODE, STATE_LOCKED, STATE_UNLOCKED
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_GIID,
    CONF_LOCK_CODE_DIGITS,
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
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Verisure alarm control panel from a config entry."""
    coordinator: VerisureDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    platform = async_get_current_platform()
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


class VerisureDoorlock(CoordinatorEntity[VerisureDataUpdateCoordinator], LockEntity):
    """Representation of a Verisure doorlock."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, coordinator: VerisureDataUpdateCoordinator, serial_number: str
    ) -> None:
        """Initialize the Verisure lock."""
        super().__init__(coordinator)
        self._attr_unique_id = serial_number

        self.serial_number = serial_number
        self._state: str | None = None
        self._digits = coordinator.entry.options.get(
            CONF_LOCK_CODE_DIGITS, DEFAULT_LOCK_CODE_DIGITS
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        area = self.coordinator.data["locks"][self.serial_number]["device"]["area"]
        return DeviceInfo(
            name=area,
            suggested_area=area,
            manufacturer="Verisure",
            model="Lockguard Smartlock",
            identifiers={(DOMAIN, self.serial_number)},
            via_device=(DOMAIN, self.coordinator.entry.data[CONF_GIID]),
            configuration_url="https://mypages.verisure.com",
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available and self.serial_number in self.coordinator.data["locks"]
        )

    @property
    def changed_by(self) -> str | None:
        """Last change triggered by."""
        return (
            self.coordinator.data["locks"][self.serial_number]
            .get("user", {})
            .get("name")
        )

    @property
    def changed_method(self) -> str:
        """Last change method."""
        return self.coordinator.data["locks"][self.serial_number]["lockMethod"]

    @property
    def code_format(self) -> str:
        """Return the required six digit code."""
        return "^\\d{%s}$" % self._digits

    @property
    def is_locked(self) -> bool:
        """Return true if lock is locked."""
        return (
            self.coordinator.data["locks"][self.serial_number]["lockStatus"] == "LOCKED"
        )

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the state attributes."""
        return {"method": self.changed_method}

    async def async_unlock(self, **kwargs: Any) -> None:
        """Send unlock command."""
        code = kwargs.get(ATTR_CODE)
        if code:
            await self.async_set_lock_state(code, STATE_UNLOCKED)

    async def async_lock(self, **kwargs: Any) -> None:
        """Send lock command."""
        code = kwargs.get(ATTR_CODE)
        if code:
            await self.async_set_lock_state(code, STATE_LOCKED)

    async def async_set_lock_state(self, code: str, state: str) -> None:
        """Send set lock state command."""
        command = (
            self.coordinator.verisure.door_lock(self.serial_number, code)
            if state == STATE_LOCKED
            else self.coordinator.verisure.door_unlock(self.serial_number, code)
        )
        lock_request = await self.hass.async_add_executor_job(
            self.coordinator.verisure.request,
            command,
        )
        LOGGER.debug("Verisure doorlock %s", state)
        transaction_id = lock_request.get("data", {}).get(command["operationName"])
        target_state = "LOCKED" if state == STATE_LOCKED else "UNLOCKED"
        lock_status = None
        attempts = 0
        while lock_status != "OK":
            if attempts == 30:
                break
            if attempts > 1:
                await asyncio.sleep(0.5)
            attempts += 1
            poll_data = await self.hass.async_add_executor_job(
                self.coordinator.verisure.request,
                self.coordinator.verisure.poll_lock_state(
                    transaction_id, self.serial_number, target_state
                ),
            )
            lock_status = (
                poll_data.get("data", {})
                .get("installation", {})
                .get("doorLockStateChangePollResult", {})
                .get("result")
            )
        if lock_status == "OK":
            self._state = state

    def disable_autolock(self) -> None:
        """Disable autolock on a doorlock."""
        try:
            command = self.coordinator.verisure.set_autolock_enabled(
                self.serial_number, auto_lock_enabled=False
            )
            self.coordinator.verisure.request(command)
            LOGGER.debug("Disabling autolock on %s", self.serial_number)
        except VerisureError as ex:
            LOGGER.error("Could not disable autolock, %s", ex)

    def enable_autolock(self) -> None:
        """Enable autolock on a doorlock."""
        try:
            command = self.coordinator.verisure.set_autolock_enabled(
                self.serial_number, auto_lock_enabled=True
            )
            self.coordinator.verisure.request(command)
            LOGGER.debug("Enabling autolock on %s", self.serial_number)
        except VerisureError as ex:
            LOGGER.error("Could not enable autolock, %s", ex)
