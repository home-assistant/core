"""Support for Verisure locks."""
from __future__ import annotations

from time import sleep
from typing import Any, Callable

from homeassistant.components.lock import LockEntity
from homeassistant.const import ATTR_CODE, STATE_LOCKED, STATE_UNLOCKED
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import VerisureDataUpdateCoordinator
from .const import CONF_CODE_DIGITS, CONF_DEFAULT_LOCK_CODE, CONF_LOCKS, DOMAIN, LOGGER


def setup_platform(
    hass: HomeAssistant,
    config: dict[str, Any],
    add_entities: Callable[[list[Entity], bool], None],
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Set up the Verisure lock platform."""
    coordinator = hass.data[DOMAIN]
    locks = []
    if int(coordinator.config.get(CONF_LOCKS, 1)):
        locks.extend(
            [
                VerisureDoorlock(coordinator, device_label)
                for device_label in coordinator.get(
                    "$.doorLockStatusList[*].deviceLabel"
                )
            ]
        )

    add_entities(locks)


class VerisureDoorlock(CoordinatorEntity, LockEntity):
    """Representation of a Verisure doorlock."""

    coordinator: VerisureDataUpdateCoordinator

    def __init__(
        self, coordinator: VerisureDataUpdateCoordinator, device_label: str
    ) -> None:
        """Initialize the Verisure lock."""
        super().__init__(coordinator)
        self._device_label = device_label
        self._state = None
        self._digits = coordinator.config.get(CONF_CODE_DIGITS)
        self._default_lock_code = coordinator.config.get(CONF_DEFAULT_LOCK_CODE)

    @property
    def name(self) -> str:
        """Return the name of the lock."""
        return self.coordinator.get_first(
            "$.doorLockStatusList[?(@.deviceLabel=='%s')].area", self._device_label
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.get_first(
                "$.doorLockStatusList[?(@.deviceLabel=='%s')]", self._device_label
            )
            is not None
        )

    @property
    def changed_by(self) -> str | None:
        """Last change triggered by."""
        return self.coordinator.get_first(
            "$.doorLockStatusList[?(@.deviceLabel=='%s')].userString",
            self._device_label,
        )

    @property
    def code_format(self) -> str:
        """Return the required six digit code."""
        return "^\\d{%s}$" % self._digits

    @property
    def is_locked(self) -> bool:
        """Return true if lock is locked."""
        status = self.coordinator.get_first(
            "$.doorLockStatusList[?(@.deviceLabel=='%s')].lockedState",
            self._device_label,
        )
        return status == "LOCKED"

    def unlock(self, **kwargs) -> None:
        """Send unlock command."""
        code = kwargs.get(ATTR_CODE, self._default_lock_code)
        if code is None:
            LOGGER.error("Code required but none provided")
            return

        self.set_lock_state(code, STATE_UNLOCKED)

    def lock(self, **kwargs) -> None:
        """Send lock command."""
        code = kwargs.get(ATTR_CODE, self._default_lock_code)
        if code is None:
            LOGGER.error("Code required but none provided")
            return

        self.set_lock_state(code, STATE_LOCKED)

    def set_lock_state(self, code: str, state: str) -> None:
        """Send set lock state command."""
        lock_state = "lock" if state == STATE_LOCKED else "unlock"
        transaction_id = self.coordinator.session.set_lock_state(
            code, self._device_label, lock_state
        )["doorLockStateChangeTransactionId"]
        LOGGER.debug("Verisure doorlock %s", state)
        transaction = {}
        attempts = 0
        while "result" not in transaction:
            transaction = self.coordinator.session.get_lock_state_transaction(
                transaction_id
            )
            attempts += 1
            if attempts == 30:
                break
            if attempts > 1:
                sleep(0.5)
        if transaction["result"] == "OK":
            self._state = state
