"""Test Duosida EV coordinator."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant

from homeassistant.components.duosida_ev.coordinator import (
    DuosidaDataUpdateCoordinator,
    MAX_RETRY_ATTEMPTS,
)


@pytest.fixture
async def coordinator(
    hass: HomeAssistant, mock_charger: Any
) -> AsyncGenerator[DuosidaDataUpdateCoordinator, None]:
    """Return a coordinator instance."""
    coord = DuosidaDataUpdateCoordinator(
        hass,
        mock_charger,
        device_id="03123456789012345678",
    )
    yield coord
    # Cleanup: unschedule any pending refreshes
    coord._unschedule_refresh()


async def test_coordinator_update_success(
    hass: HomeAssistant,
    coordinator: DuosidaDataUpdateCoordinator,
) -> None:
    """Test coordinator successfully updates data."""
    with (
        patch.object(coordinator._store, "async_load", return_value=None),
        patch.object(coordinator._store, "async_save", return_value=None),
    ):
        await coordinator.async_refresh()

        assert coordinator.data is not None
        assert coordinator.data["conn_status"] == 2  # Charging
        assert coordinator.data["voltage"] == 230.0
        assert coordinator.data["current"] == 16.0
        assert coordinator.data["power"] == 11040


async def test_coordinator_update_connection_error(
    hass: HomeAssistant,
    coordinator: DuosidaDataUpdateCoordinator,
) -> None:
    """Test coordinator handles connection errors."""
    # Make the charger raise an error
    coordinator.charger.connect = MagicMock(return_value=False)

    await coordinator.async_refresh()

    # After failed refresh, last_update_success should be False
    assert coordinator.last_update_success is False


async def test_coordinator_set_max_current(
    hass: HomeAssistant,
    coordinator: DuosidaDataUpdateCoordinator,
) -> None:
    """Test coordinator can set max current."""
    import asyncio

    with (
        patch.object(coordinator._store, "async_load", return_value=None),
        patch.object(coordinator._store, "async_save", return_value=None),
    ):
        # First refresh to get initial data
        await coordinator.async_refresh()

        # Set max current
        result = await coordinator.async_set_max_current(20)
        assert result is True

        # Verify the setting was persisted
        assert coordinator.get_stored_setting("max_current") == 20

        # Allow any pending tasks to complete
        await asyncio.sleep(0.1)
        await hass.async_block_till_done()


async def test_coordinator_set_led_brightness(
    hass: HomeAssistant,
    coordinator: DuosidaDataUpdateCoordinator,
) -> None:
    """Test coordinator can set LED brightness."""
    with (
        patch.object(coordinator._store, "async_load", return_value=None),
        patch.object(coordinator._store, "async_save", return_value=None),
    ):
        await coordinator.async_refresh()

        # Set LED brightness (valid values: 0, 1, 3)
        result = await coordinator.async_set_led_brightness(3)
        assert result is True

        assert coordinator.get_stored_setting("led_brightness") == 3


async def test_coordinator_set_direct_mode(
    hass: HomeAssistant,
    coordinator: DuosidaDataUpdateCoordinator,
) -> None:
    """Test coordinator can set direct mode."""
    with (
        patch.object(coordinator._store, "async_load", return_value=None),
        patch.object(coordinator._store, "async_save", return_value=None),
    ):
        await coordinator.async_refresh()

        result = await coordinator.async_set_direct_mode(True)
        assert result is True

        assert coordinator.get_stored_setting("direct_mode") is True


async def test_coordinator_start_charging(
    hass: HomeAssistant,
    coordinator: DuosidaDataUpdateCoordinator,
) -> None:
    """Test coordinator can start charging."""
    import asyncio

    with (
        patch.object(coordinator._store, "async_load", return_value=None),
        patch.object(coordinator._store, "async_save", return_value=None),
    ):
        await coordinator.async_refresh()

        result = await coordinator.async_start_charging()
        assert result is True

        # Allow any pending tasks to complete
        await asyncio.sleep(0.1)
        await hass.async_block_till_done()


async def test_coordinator_stop_charging(
    hass: HomeAssistant,
    coordinator: DuosidaDataUpdateCoordinator,
) -> None:
    """Test coordinator can stop charging."""
    import asyncio

    with (
        patch.object(coordinator._store, "async_load", return_value=None),
        patch.object(coordinator._store, "async_save", return_value=None),
    ):
        await coordinator.async_refresh()

        result = await coordinator.async_stop_charging()
        assert result is True

        # Allow any pending tasks to complete
        await asyncio.sleep(0.1)
        await hass.async_block_till_done()


async def test_coordinator_energy_integration(
    hass: HomeAssistant,
    coordinator: DuosidaDataUpdateCoordinator,
) -> None:
    """Test coordinator integrates power to calculate total energy."""
    with (
        patch.object(coordinator._store, "async_load", return_value=None),
        patch.object(coordinator._store, "async_save", return_value=None),
    ):
        await coordinator.async_refresh()

        # Get initial energy
        initial_energy = coordinator.data["total_energy"]

        # Manually simulate a time delta and power consumption
        # Set last update to 1 hour ago (3600 seconds)
        current_time = hass.loop.time()
        coordinator._stored_settings["last_update_time"] = current_time - 3600.0
        coordinator._stored_settings["last_power"] = 11040.0  # 11.04 kW
        coordinator._stored_settings["total_energy"] = initial_energy

        # Set charger to still be at 11.04 kW
        coordinator.charger._status["power"] = 11040

        # Do another update - should integrate the power over the 1-hour gap
        await coordinator._async_update_data()
        energy_after_update = coordinator.data["total_energy"]

        # Energy should have increased
        # 11.04 kW * 1 hour = 11.04 kWh (approximately)
        assert energy_after_update > initial_energy
        # Should be roughly 11 kWh more (11040W * 1h / 1000 = 11.04 kWh)
        assert energy_after_update - initial_energy > 10.0


async def test_coordinator_reset_total_energy(
    hass: HomeAssistant,
    coordinator: DuosidaDataUpdateCoordinator,
) -> None:
    """Test coordinator can reset total energy."""
    import asyncio

    with (
        patch.object(coordinator._store, "async_load", return_value=None),
        patch.object(coordinator._store, "async_save", return_value=None),
    ):
        await coordinator.async_refresh()

        # Set some energy value
        coordinator._stored_settings["total_energy"] = 100.0

        # Reset
        await coordinator.async_reset_total_energy()

        assert coordinator.get_stored_setting("total_energy") == 0.0

        # Allow any pending tasks to complete
        await asyncio.sleep(0.1)
        await hass.async_block_till_done()


async def test_coordinator_settings_persistence(
    hass: HomeAssistant,
    coordinator: DuosidaDataUpdateCoordinator,
) -> None:
    """Test coordinator persists settings to storage."""
    import asyncio

    with (
        patch.object(coordinator._store, "async_load", return_value=None),
        patch.object(coordinator._store, "async_save", return_value=None),
    ):
        await coordinator.async_load_stored_settings()
        await coordinator.async_refresh()

        # Set multiple settings
        await coordinator.async_set_led_brightness(3)
        await coordinator.async_set_direct_mode(True)
        await coordinator.async_set_max_current(20)

        # Settings should be persisted
        assert coordinator.get_stored_setting("led_brightness") == 3
        assert coordinator.get_stored_setting("direct_mode") is True
        assert coordinator.get_stored_setting("max_current") == 20

        # Allow any pending tasks to complete
        await asyncio.sleep(0.1)
        await hass.async_block_till_done()


async def test_coordinator_unknown_first_approach(
    hass: HomeAssistant,
    coordinator: DuosidaDataUpdateCoordinator,
) -> None:
    """Test coordinator doesn't set defaults, keeps settings as unknown."""
    with patch.object(coordinator._store, "async_load", return_value=None):
        await coordinator.async_load_stored_settings()

    # Before any user interaction, settings should be None (unknown)
    assert coordinator.get_stored_setting("led_brightness") is None
    assert coordinator.get_stored_setting("direct_mode") is None
    assert coordinator.get_stored_setting("max_voltage") is None
    assert coordinator.get_stored_setting("min_voltage") is None


async def test_coordinator_set_max_voltage(
    hass: HomeAssistant,
    coordinator: DuosidaDataUpdateCoordinator,
) -> None:
    """Test coordinator can set max voltage."""
    with (
        patch.object(coordinator._store, "async_load", return_value=None),
        patch.object(coordinator._store, "async_save", return_value=None),
    ):
        await coordinator.async_refresh()

        result = await coordinator.async_set_max_voltage(280)
        assert result is True

        assert coordinator.get_stored_setting("max_voltage") == 280


async def test_coordinator_set_min_voltage(
    hass: HomeAssistant,
    coordinator: DuosidaDataUpdateCoordinator,
) -> None:
    """Test coordinator can set min voltage."""
    with (
        patch.object(coordinator._store, "async_load", return_value=None),
        patch.object(coordinator._store, "async_save", return_value=None),
    ):
        await coordinator.async_refresh()

        result = await coordinator.async_set_min_voltage(90)
        assert result is True

        assert coordinator.get_stored_setting("min_voltage") == 90


async def test_coordinator_disconnect(
    hass: HomeAssistant,
    coordinator: DuosidaDataUpdateCoordinator,
) -> None:
    """Test coordinator disconnect is a no-op since connections are not persistent."""
    with (
        patch.object(coordinator._store, "async_load", return_value=None),
        patch.object(coordinator._store, "async_save", return_value=None),
    ):
        await coordinator.async_refresh()

        # After refresh, charger should be disconnected (coordinator disconnects after each poll)
        assert coordinator.charger._connected is False

        # Disconnect is a no-op
        coordinator.disconnect()

        # Charger should still be disconnected
        assert coordinator.charger._connected is False


async def test_coordinator_connection_retry_success_on_second_attempt(
    hass: HomeAssistant,
    coordinator: DuosidaDataUpdateCoordinator,
) -> None:
    """Test coordinator retries and succeeds on second attempt."""
    import asyncio

    # Make first connection attempt fail, second succeed
    call_count = 0

    def connect_side_effect() -> bool:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return False  # First attempt fails
        coordinator.charger._connected = True
        return True  # Second attempt succeeds

    coordinator.charger.connect = MagicMock(side_effect=connect_side_effect)

    # Should succeed after retry
    result = await coordinator._async_connect_with_retry()
    assert result is True
    assert call_count == 2  # Two attempts

    # Allow any pending tasks to complete
    await asyncio.sleep(0.1)
    await hass.async_block_till_done()


async def test_coordinator_connection_retry_all_attempts_fail(
    hass: HomeAssistant,
    coordinator: DuosidaDataUpdateCoordinator,
) -> None:
    """Test coordinator exhausts all retry attempts."""
    import asyncio

    # Make all connection attempts fail
    coordinator.charger.connect = MagicMock(return_value=False)

    # Should fail after all retries
    result = await coordinator._async_connect_with_retry()
    assert result is False

    # Should have tried MAX_RETRY_ATTEMPTS times (3)
    assert coordinator.charger.connect.call_count == MAX_RETRY_ATTEMPTS

    # Allow any pending tasks to complete
    await asyncio.sleep(0.1)
    await hass.async_block_till_done()


async def test_coordinator_connection_retry_with_exception(
    hass: HomeAssistant,
    coordinator: DuosidaDataUpdateCoordinator,
) -> None:
    """Test coordinator retries when connection raises exception."""
    import asyncio

    # Make connection raise exception on first attempt, succeed on second
    call_count = 0

    def connect_side_effect() -> bool:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("Network unreachable")
        coordinator.charger._connected = True
        return True

    coordinator.charger.connect = MagicMock(side_effect=connect_side_effect)

    # Should recover from exception and succeed
    result = await coordinator._async_connect_with_retry()
    assert result is True
    assert call_count == 2

    # Allow any pending tasks to complete
    await asyncio.sleep(0.1)
    await hass.async_block_till_done()


async def test_coordinator_load_stored_settings_with_data(
    hass: HomeAssistant,
    coordinator: DuosidaDataUpdateCoordinator,
) -> None:
    """Test loading stored settings when data exists in storage."""
    stored_data = {
        "max_current": 25,
        "led_brightness": 1,
        "total_energy": 50.5,
    }

    with patch.object(coordinator._store, "async_load", return_value=stored_data):
        await coordinator.async_load_stored_settings()

        # Verify settings were loaded
        assert coordinator._stored_settings["max_current"] == 25
        assert coordinator._stored_settings["led_brightness"] == 1
        assert coordinator._stored_settings["total_energy"] == 50.5


async def test_coordinator_command_failure_paths(
    hass: HomeAssistant,
    coordinator: DuosidaDataUpdateCoordinator,
) -> None:
    """Test coordinator handles command failures gracefully."""
    with (
        patch.object(coordinator._store, "async_load", return_value=None),
        patch.object(coordinator._store, "async_save", return_value=None),
    ):
        # Test set_max_current failure
        with patch.object(coordinator.charger, "set_max_current", return_value=False):
            result = await coordinator.async_set_max_current(20)
            assert result is False

        # Test set_led_brightness failure
        with patch.object(coordinator.charger, "set_led_brightness", return_value=False):
            result = await coordinator.async_set_led_brightness(3)
            assert result is False

        # Test set_direct_mode failure
        with patch.object(
            coordinator.charger, "set_direct_work_mode", return_value=False
        ):
            result = await coordinator.async_set_direct_mode(True)
            assert result is False

        # Test set_stop_on_disconnect failure
        with patch.object(
            coordinator.charger, "set_stop_on_disconnect", return_value=False
        ):
            result = await coordinator.async_set_stop_on_disconnect(True)
            assert result is False

        # Test set_max_voltage failure
        with patch.object(coordinator.charger, "set_max_voltage", return_value=False):
            result = await coordinator.async_set_max_voltage(280)
            assert result is False

        # Test set_min_voltage failure
        with patch.object(coordinator.charger, "set_min_voltage", return_value=False):
            result = await coordinator.async_set_min_voltage(90)
            assert result is False


async def test_coordinator_command_exceptions(
    hass: HomeAssistant,
    coordinator: DuosidaDataUpdateCoordinator,
) -> None:
    """Test coordinator handles exceptions in commands."""
    with (
        patch.object(coordinator._store, "async_load", return_value=None),
        patch.object(coordinator._store, "async_save", return_value=None),
    ):
        # Test exception in set_max_current
        with patch.object(
            coordinator.charger, "set_max_current", side_effect=Exception("Test error")
        ):
            result = await coordinator.async_set_max_current(20)
            assert result is False

        # Test exception in start_charging
        with patch.object(
            coordinator.charger, "start_charging", side_effect=Exception("Test error")
        ):
            result = await coordinator.async_start_charging()
            assert result is False

        # Test exception in stop_charging
        with patch.object(
            coordinator.charger, "stop_charging", side_effect=Exception("Test error")
        ):
            result = await coordinator.async_stop_charging()
            assert result is False


async def test_coordinator_sync_settings_to_charger(
    hass: HomeAssistant,
    coordinator: DuosidaDataUpdateCoordinator,
) -> None:
    """Test coordinator syncs stored settings to charger on first connection."""
    # Pre-load settings with user-configured values
    stored_data = {
        "max_current": 20,
        "led_brightness": 3,
        "direct_mode": True,
        "stop_on_disconnect": False,
        "max_voltage": 280,
        "min_voltage": 90,
        "total_energy": 100.0,
    }

    with (
        patch.object(coordinator._store, "async_load", return_value=stored_data),
        patch.object(coordinator._store, "async_save", return_value=None),
    ):
        # Load settings
        await coordinator.async_load_stored_settings()

        # Verify settings were loaded
        assert coordinator._stored_settings["max_current"] == 20
        assert coordinator._stored_settings["led_brightness"] == 3
        assert coordinator._stored_settings["direct_mode"] is True
        assert coordinator._stored_settings["stop_on_disconnect"] is False
        assert coordinator._stored_settings["max_voltage"] == 280
        assert coordinator._stored_settings["min_voltage"] == 90

        # Now do a refresh which should trigger settings sync
        await coordinator.async_refresh()

        # Verify sync happened by checking the flag
        assert coordinator._settings_synced_this_session is True


async def test_coordinator_set_stop_on_disconnect_success(
    hass: HomeAssistant,
    coordinator: DuosidaDataUpdateCoordinator,
) -> None:
    """Test coordinator can set stop on disconnect."""
    with (
        patch.object(coordinator._store, "async_load", return_value=None),
        patch.object(coordinator._store, "async_save", return_value=None),
    ):
        await coordinator.async_refresh()

        # Set stop on disconnect
        result = await coordinator.async_set_stop_on_disconnect(True)
        assert result is True

        # Verify the setting was persisted
        assert coordinator.get_stored_setting("stop_on_disconnect") is True


async def test_coordinator_update_data_get_status_returns_none(
    hass: HomeAssistant,
    coordinator: DuosidaDataUpdateCoordinator,
) -> None:
    """Test coordinator raises UpdateFailed when get_status returns None."""
    from homeassistant.helpers.update_coordinator import UpdateFailed

    with (
        patch.object(coordinator._store, "async_load", return_value=None),
        patch.object(coordinator._store, "async_save", return_value=None),
    ):
        # Make get_status return None
        coordinator.charger.get_status = MagicMock(return_value=None)

        # Should raise UpdateFailed
        with pytest.raises(UpdateFailed, match="Failed to get status"):
            await coordinator._async_update_data()


async def test_coordinator_update_data_exception(
    hass: HomeAssistant,
    coordinator: DuosidaDataUpdateCoordinator,
) -> None:
    """Test coordinator handles generic exception in update."""
    from homeassistant.helpers.update_coordinator import UpdateFailed

    with (
        patch.object(coordinator._store, "async_load", return_value=None),
        patch.object(coordinator._store, "async_save", return_value=None),
    ):
        # Make get_status raise an exception
        coordinator.charger.get_status = MagicMock(
            side_effect=RuntimeError("Unexpected error")
        )

        # Should raise UpdateFailed wrapping the exception
        with pytest.raises(UpdateFailed, match="Error communicating with charger"):
            await coordinator._async_update_data()


async def test_coordinator_send_command_connection_fails(
    hass: HomeAssistant,
    coordinator: DuosidaDataUpdateCoordinator,
) -> None:
    """Test coordinator handles connection failure in send_command."""
    import asyncio

    with (
        patch.object(coordinator._store, "async_load", return_value=None),
        patch.object(coordinator._store, "async_save", return_value=None),
    ):
        # Make all connection attempts fail
        coordinator.charger.connect = MagicMock(return_value=False)

        # Try to set LED brightness - should fail due to connection
        result = await coordinator.async_set_led_brightness(3)
        assert result is False

        # Allow any pending tasks to complete
        await asyncio.sleep(0.1)
        await hass.async_block_till_done()
