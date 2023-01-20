"""The tests for the lock component."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from homeassistant.components.lock import (
    ATTR_CODE,
    DOMAIN,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
    STATE_JAMMED,
    STATE_LOCKED,
    STATE_LOCKING,
    STATE_UNLOCKED,
    STATE_UNLOCKING,
    LockEntity,
    LockEntityFeature,
    _async_lock,
    _async_open,
    _async_unlock,
)
from homeassistant.core import HomeAssistant, ServiceCall


class MockLockEntity(LockEntity):
    """Mock lock to use in tests."""

    def __init__(
        self,
        code_format: str | None = None,
        supported_features: LockEntityFeature = LockEntityFeature(0),
    ) -> None:
        """Initialize mock lock entity."""
        self._attr_supported_features = supported_features
        self.calls_open = MagicMock()
        if code_format is not None:
            self._attr_code_format = code_format

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        self._attr_is_locking = False
        self._attr_is_locked = True

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        self._attr_is_unlocking = False
        self._attr_is_locked = False

    async def async_open(self, **kwargs: Any) -> None:
        """Open the door latch."""
        self.calls_open(kwargs)


async def test_lock_default(hass: HomeAssistant) -> None:
    """Test lock entity with defaults."""
    lock = MockLockEntity()
    lock.hass = hass

    assert lock.code_format is None
    assert lock.state is None


async def test_lock_states(hass: HomeAssistant) -> None:
    """Test lock entity states."""
    # pylint: disable=protected-access

    lock = MockLockEntity()
    lock.hass = hass

    assert lock.state is None

    lock._attr_is_locking = True
    assert lock.is_locking
    assert lock.state == STATE_LOCKING

    await _async_lock(lock, ServiceCall(DOMAIN, SERVICE_LOCK, {}))
    assert lock.is_locked
    assert lock.state == STATE_LOCKED

    lock._attr_is_unlocking = True
    assert lock.is_unlocking
    assert lock.state == STATE_UNLOCKING

    await _async_unlock(lock, ServiceCall(DOMAIN, SERVICE_UNLOCK, {}))
    assert not lock.is_locked
    assert lock.state == STATE_UNLOCKED

    lock._attr_is_jammed = True
    assert lock.is_jammed
    assert lock.state == STATE_JAMMED
    assert not lock.is_locked


async def test_lock_open_with_code(hass: HomeAssistant) -> None:
    """Test lock entity with open service."""
    lock = MockLockEntity(
        code_format=r"^\d{4}$", supported_features=LockEntityFeature.OPEN
    )
    lock.hass = hass

    assert lock.state_attributes == {"code_format": r"^\d{4}$"}

    with pytest.raises(ValueError):
        await _async_open(lock, ServiceCall(DOMAIN, SERVICE_OPEN, {}))
    with pytest.raises(ValueError):
        await _async_open(lock, ServiceCall(DOMAIN, SERVICE_OPEN, {ATTR_CODE: ""}))
    with pytest.raises(ValueError):
        await _async_open(lock, ServiceCall(DOMAIN, SERVICE_OPEN, {ATTR_CODE: "HELLO"}))
    await _async_open(lock, ServiceCall(DOMAIN, SERVICE_OPEN, {ATTR_CODE: "1234"}))
    assert lock.calls_open.call_count == 1


async def test_lock_lock_with_code(hass: HomeAssistant) -> None:
    """Test lock entity with open service."""
    lock = MockLockEntity(code_format=r"^\d{4}$")
    lock.hass = hass

    await _async_unlock(lock, ServiceCall(DOMAIN, SERVICE_UNLOCK, {ATTR_CODE: "1234"}))
    assert not lock.is_locked

    with pytest.raises(ValueError):
        await _async_lock(lock, ServiceCall(DOMAIN, SERVICE_LOCK, {}))
    with pytest.raises(ValueError):
        await _async_lock(lock, ServiceCall(DOMAIN, SERVICE_LOCK, {ATTR_CODE: ""}))
    with pytest.raises(ValueError):
        await _async_lock(lock, ServiceCall(DOMAIN, SERVICE_LOCK, {ATTR_CODE: "HELLO"}))
    await _async_lock(lock, ServiceCall(DOMAIN, SERVICE_LOCK, {ATTR_CODE: "1234"}))
    assert lock.is_locked


async def test_lock_unlock_with_code(hass: HomeAssistant) -> None:
    """Test unlock entity with open service."""
    lock = MockLockEntity(code_format=r"^\d{4}$")
    lock.hass = hass

    await _async_lock(lock, ServiceCall(DOMAIN, SERVICE_UNLOCK, {ATTR_CODE: "1234"}))
    assert lock.is_locked

    with pytest.raises(ValueError):
        await _async_unlock(lock, ServiceCall(DOMAIN, SERVICE_UNLOCK, {}))
    with pytest.raises(ValueError):
        await _async_unlock(lock, ServiceCall(DOMAIN, SERVICE_UNLOCK, {ATTR_CODE: ""}))
    with pytest.raises(ValueError):
        await _async_unlock(
            lock, ServiceCall(DOMAIN, SERVICE_UNLOCK, {ATTR_CODE: "HELLO"})
        )
    await _async_unlock(lock, ServiceCall(DOMAIN, SERVICE_UNLOCK, {ATTR_CODE: "1234"}))
    assert not lock.is_locked
