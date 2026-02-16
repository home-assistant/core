"""Test the Casper Glow coordinator."""

from unittest.mock import AsyncMock, patch

from bleak import BleakError
import pytest

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_poll_bleak_error_logs_unavailable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a BleakError during polling logs unavailable at info level once."""
    coordinator = config_entry.runtime_data

    with patch.object(
        coordinator.device,
        "query_state",
        side_effect=BleakError("connection failed"),
    ):
        await coordinator._async_poll()

    assert "Jar is unavailable" in caplog.text
    assert caplog.text.count("Jar is unavailable") == 1
    assert not coordinator.last_poll_successful

    # A second poll failure must not log again
    caplog.clear()
    with patch.object(
        coordinator.device,
        "query_state",
        side_effect=BleakError("still down"),
    ):
        await coordinator._async_poll()

    assert "Jar is unavailable" not in caplog.text


async def test_poll_generic_exception_logs_unavailable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a generic exception during polling logs unavailable at info level once."""
    coordinator = config_entry.runtime_data

    with patch.object(
        coordinator.device,
        "query_state",
        side_effect=Exception("unexpected"),
    ):
        await coordinator._async_poll()

    assert "unexpected error while polling" in caplog.text
    assert not coordinator.last_poll_successful


async def test_poll_recovery_logs_back_online(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that recovery after a failed poll logs back online at info level."""
    coordinator = config_entry.runtime_data

    # First make a poll fail
    with patch.object(
        coordinator.device,
        "query_state",
        side_effect=BleakError("gone"),
    ):
        await coordinator._async_poll()

    assert not coordinator.last_poll_successful
    caplog.clear()

    # Now recover
    with patch.object(
        coordinator.device,
        "query_state",
        new_callable=AsyncMock,
    ):
        await coordinator._async_poll()

    assert "Jar is back online" in caplog.text
    assert coordinator.last_poll_successful
