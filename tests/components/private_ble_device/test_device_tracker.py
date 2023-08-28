"""Tests for polling measures."""


import time

from homeassistant.components.bluetooth.advertisement_tracker import (
    ADVERTISING_TIMES_NEEDED,
)
from homeassistant.core import HomeAssistant

from . import (
    MAC_RPA_VALID_1,
    MAC_RPA_VALID_2,
    MAC_STATIC,
    async_inject_broadcast,
    async_mock_config_entry,
    async_move_time_forwards,
)

from tests.components.bluetooth.test_advertisement_tracker import ONE_HOUR_SECONDS


async def test_tracker_created(hass: HomeAssistant, enable_bluetooth: None) -> None:
    """Test creating a tracker entity when no devices have been seen."""
    await async_mock_config_entry(hass)

    state = hass.states.get("device_tracker.private_ble_device_000000")
    assert state
    assert state.state == "not_home"


async def test_tracker_ignore_other_rpa(
    hass: HomeAssistant, enable_bluetooth: None
) -> None:
    """Test that tracker ignores RPA's that don't match us."""
    await async_mock_config_entry(hass)
    await async_inject_broadcast(hass, MAC_STATIC)

    state = hass.states.get("device_tracker.private_ble_device_000000")
    assert state
    assert state.state == "not_home"


async def test_tracker_already_home(
    hass: HomeAssistant, enable_bluetooth: None
) -> None:
    """Test creating a tracker and the device was already discovered by HA."""
    await async_inject_broadcast(hass, MAC_RPA_VALID_1)
    await async_mock_config_entry(hass)

    state = hass.states.get("device_tracker.private_ble_device_000000")
    assert state
    assert state.state == "home"


async def test_tracker_arrive_home(hass: HomeAssistant, enable_bluetooth: None) -> None:
    """Test transition from not_home to home."""
    await async_mock_config_entry(hass)
    await async_inject_broadcast(hass, MAC_RPA_VALID_1, b"1")
    state = hass.states.get("device_tracker.private_ble_device_000000")
    assert state
    assert state.state == "home"
    assert state.attributes["current_address"] == "40:01:02:0a:c4:a6"
    assert state.attributes["source"] == "local"

    await async_inject_broadcast(hass, MAC_STATIC, b"1")
    state = hass.states.get("device_tracker.private_ble_device_000000")
    assert state
    assert state.state == "home"

    # Test same wrong mac address again to exercise some caching
    await async_inject_broadcast(hass, MAC_STATIC, b"2")
    state = hass.states.get("device_tracker.private_ble_device_000000")
    assert state
    assert state.state == "home"

    # And test original mac address again.
    # Use different mfr data so that event bubbles up
    await async_inject_broadcast(hass, MAC_RPA_VALID_1, b"2")
    state = hass.states.get("device_tracker.private_ble_device_000000")
    assert state
    assert state.state == "home"
    assert state.attributes["current_address"] == "40:01:02:0a:c4:a6"


async def test_tracker_mac_rotate(hass: HomeAssistant, enable_bluetooth: None) -> None:
    """Test MAC address rotation."""
    await async_inject_broadcast(hass, MAC_RPA_VALID_1)
    await async_mock_config_entry(hass)

    state = hass.states.get("device_tracker.private_ble_device_000000")
    assert state
    assert state.state == "home"
    assert state.attributes["current_address"] == MAC_RPA_VALID_1

    await async_inject_broadcast(hass, MAC_RPA_VALID_2)
    state = hass.states.get("device_tracker.private_ble_device_000000")
    assert state
    assert state.state == "home"
    assert state.attributes["current_address"] == MAC_RPA_VALID_2


async def test_tracker_start_stale(hass: HomeAssistant, enable_bluetooth: None) -> None:
    """Test edge case where we find an existing stale record, and it expires before we see any more."""
    time.monotonic()

    await async_inject_broadcast(hass, MAC_RPA_VALID_1)
    await async_mock_config_entry(hass)

    state = hass.states.get("device_tracker.private_ble_device_000000")
    assert state
    assert state.state == "home"

    await async_move_time_forwards(
        hass, ((ADVERTISING_TIMES_NEEDED - 1) * ONE_HOUR_SECONDS)
    )
    state = hass.states.get("device_tracker.private_ble_device_000000")
    assert state
    assert state.state == "not_home"


async def test_tracker_leave_home(hass: HomeAssistant, enable_bluetooth: None) -> None:
    """Test tracker notices we have left."""
    time.monotonic()

    await async_mock_config_entry(hass)
    await async_inject_broadcast(hass, MAC_RPA_VALID_1)

    state = hass.states.get("device_tracker.private_ble_device_000000")
    assert state
    assert state.state == "home"

    await async_move_time_forwards(
        hass, ((ADVERTISING_TIMES_NEEDED - 1) * ONE_HOUR_SECONDS)
    )
    state = hass.states.get("device_tracker.private_ble_device_000000")
    assert state
    assert state.state == "not_home"


async def test_old_tracker_leave_home(
    hass: HomeAssistant, enable_bluetooth: None
) -> None:
    """Test tracker ignores an old stale mac address timing out."""
    start_time = time.monotonic()

    await async_mock_config_entry(hass)

    await async_inject_broadcast(hass, MAC_RPA_VALID_2, broadcast_time=start_time)
    await async_inject_broadcast(hass, MAC_RPA_VALID_2, broadcast_time=start_time + 15)

    state = hass.states.get("device_tracker.private_ble_device_000000")
    assert state
    assert state.state == "home"

    # First address has timed out - still home
    await async_move_time_forwards(hass, 910)
    state = hass.states.get("device_tracker.private_ble_device_000000")
    assert state
    assert state.state == "home"

    # Second address has time out - now away
    await async_move_time_forwards(hass, 920)
    state = hass.states.get("device_tracker.private_ble_device_000000")
    assert state
    assert state.state == "not_home"
