"""Test Yale Access Bluetooth auto-lock entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from yalexs_ble.const import (
    AutoLockMode,
    AutoLockState,
    ConnectionInfo,
    DoorStatus,
    LockInfo,
    LockState,
    LockStatus,
)

from homeassistant.components.yalexs_ble.models import YaleXSBLEData
from homeassistant.components.yalexs_ble.select import (
    YaleXSBLEAutoLockTimingSelect,
    YaleXSBLEAutoLockWhenSelect,
    YaleXSBLERelockTimingSelect,
)
from homeassistant.components.yalexs_ble.switch import YaleXSBLEAutoLockSwitch


@pytest.fixture
def lock() -> MagicMock:
    """Return a mocked lock."""
    lock = MagicMock()
    lock.address = "AA:BB:CC:DD:EE:FF"
    lock.lock_info = LockInfo("Yale", "L7002DT", "serial", "1.0")
    lock.connection_info = ConnectionInfo(-60)
    lock.lock_state = _lock_state(AutoLockState(AutoLockMode.INSTANT, 60))
    lock.auto_lock_prev = None
    lock.set_auto_lock_duration = AsyncMock()
    lock.set_auto_lock_mode = AsyncMock()
    return lock


@pytest.fixture
def data(lock: MagicMock) -> YaleXSBLEData:
    """Return Yale XS BLE runtime data."""
    return YaleXSBLEData("Ytterdorr", lock, False)


def _lock_state(auto_lock: AutoLockState | None) -> LockState:
    """Return a lock state with the given auto-lock state."""
    return LockState(
        LockStatus.LOCKED,
        DoorStatus.CLOSED,
        None,
        None,
        auto_lock,
        None,
    )


def test_auto_lock_when_select_options(data: YaleXSBLEData) -> None:
    """Test the auto-lock when select follows the lock auto-lock mode."""
    entity = YaleXSBLEAutoLockWhenSelect(data)

    assert entity.current_option == "instant"

    entity._async_update_state(  # noqa: SLF001
        _lock_state(AutoLockState(AutoLockMode.TIMER, 60)),
        data.lock.lock_info,
        data.lock.connection_info,
    )
    assert entity.current_option == "on_timer"

    entity._async_update_state(  # noqa: SLF001
        _lock_state(AutoLockState(AutoLockMode.OFF, 0)),
        data.lock.lock_info,
        data.lock.connection_info,
    )
    assert entity.current_option is None


async def test_auto_lock_when_select_sets_mode(data: YaleXSBLEData) -> None:
    """Test selecting when auto-lock should happen sets the mode."""
    entity = YaleXSBLEAutoLockWhenSelect(data)

    await entity.async_select_option("on_timer")

    data.lock.set_auto_lock_mode.assert_awaited_once_with(AutoLockMode.TIMER)


def test_timing_selects_follow_matching_auto_lock_mode(data: YaleXSBLEData) -> None:
    """Test timing selects only show state for their matching auto-lock mode."""
    auto_lock_timing = YaleXSBLEAutoLockTimingSelect(data)
    relock_timing = YaleXSBLERelockTimingSelect(data)

    assert auto_lock_timing.current_option is None
    assert relock_timing.current_option == "1_min"

    state = _lock_state(AutoLockState(AutoLockMode.TIMER, 90))
    auto_lock_timing._async_update_state(  # noqa: SLF001
        state, data.lock.lock_info, data.lock.connection_info
    )
    relock_timing._async_update_state(  # noqa: SLF001
        state, data.lock.lock_info, data.lock.connection_info
    )

    assert auto_lock_timing.current_option == "1_min_30_s"
    assert relock_timing.current_option is None


async def test_timing_selects_set_duration(data: YaleXSBLEData) -> None:
    """Test timing selects set the auto-lock duration."""
    entity = YaleXSBLEAutoLockTimingSelect(data)

    await entity.async_select_option("30_s")

    data.lock.set_auto_lock_duration.assert_awaited_once_with(30)


async def test_auto_lock_switch(data: YaleXSBLEData) -> None:
    """Test auto-lock switch state and commands."""
    entity = YaleXSBLEAutoLockSwitch(data)

    assert entity.is_on is True

    entity._async_update_state(  # noqa: SLF001
        _lock_state(AutoLockState(AutoLockMode.OFF, 0)),
        data.lock.lock_info,
        data.lock.connection_info,
    )
    assert entity.is_on is False

    await entity.async_turn_off()
    data.lock.set_auto_lock_duration.assert_awaited_once_with(0)

    data.lock.auto_lock_prev = AutoLockState(AutoLockMode.TIMER, 60)
    await entity.async_turn_on()
    data.lock.set_auto_lock_mode.assert_awaited_once_with(AutoLockMode.TIMER)
