"""Tests for the Mitsubishi Comfort coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.mitsubishi_comfort.coordinator import (
    MAX_FAILURES_BEFORE_UNAVAILABLE,
    MitsubishiComfortCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


async def test_successful_update_resets_failures(
    hass: HomeAssistant,
) -> None:
    """Test that a successful update resets the failure counter."""
    device = MagicMock()
    device.serial = "SERIAL001"
    device.name = "Living Room"
    device.update_status = AsyncMock(return_value=True)

    coordinator = MitsubishiComfortCoordinator(hass, device)
    coordinator._consecutive_failures = 2

    await coordinator._async_update_data()

    assert coordinator._consecutive_failures == 0
    assert coordinator.available is True


async def test_failed_update_increments_failures(
    hass: HomeAssistant,
) -> None:
    """Test that a failed update increments the failure counter."""
    device = MagicMock()
    device.serial = "SERIAL001"
    device.name = "Living Room"
    device.update_status = AsyncMock(return_value=False)

    coordinator = MitsubishiComfortCoordinator(hass, device)

    await coordinator._async_update_data()

    assert coordinator._consecutive_failures == 1
    assert coordinator.available is True


async def test_unavailable_after_max_failures(
    hass: HomeAssistant,
) -> None:
    """Test that device becomes unavailable after MAX_FAILURES_BEFORE_UNAVAILABLE."""
    device = MagicMock()
    device.serial = "SERIAL001"
    device.name = "Living Room"
    device.update_status = AsyncMock(return_value=False)

    coordinator = MitsubishiComfortCoordinator(hass, device)
    coordinator._consecutive_failures = MAX_FAILURES_BEFORE_UNAVAILABLE - 1

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    assert coordinator._consecutive_failures == MAX_FAILURES_BEFORE_UNAVAILABLE
    assert coordinator.available is False


async def test_recovery_after_failures(
    hass: HomeAssistant,
) -> None:
    """Test that device recovers after failures when update succeeds."""
    device = MagicMock()
    device.serial = "SERIAL001"
    device.name = "Living Room"
    device.update_status = AsyncMock(return_value=True)

    coordinator = MitsubishiComfortCoordinator(hass, device)
    coordinator._consecutive_failures = MAX_FAILURES_BEFORE_UNAVAILABLE
    assert coordinator.available is False

    await coordinator._async_update_data()

    assert coordinator._consecutive_failures == 0
    assert coordinator.available is True


async def test_available_boundary(
    hass: HomeAssistant,
) -> None:
    """Test the boundary condition for availability."""
    device = MagicMock()
    device.serial = "SERIAL001"
    device.name = "Living Room"
    device.update_status = AsyncMock(return_value=False)

    coordinator = MitsubishiComfortCoordinator(hass, device)

    # Just below threshold - still available
    coordinator._consecutive_failures = MAX_FAILURES_BEFORE_UNAVAILABLE - 1
    assert coordinator.available is True

    # At threshold - unavailable
    coordinator._consecutive_failures = MAX_FAILURES_BEFORE_UNAVAILABLE
    assert coordinator.available is False


async def test_coordinator_name(
    hass: HomeAssistant,
) -> None:
    """Test coordinator name includes device serial."""
    device = MagicMock()
    device.serial = "SERIAL001"
    device.name = "Living Room"

    coordinator = MitsubishiComfortCoordinator(hass, device)

    assert coordinator.name == "mitsubishi_comfort_SERIAL001"
