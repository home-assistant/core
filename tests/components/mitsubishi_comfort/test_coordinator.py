"""Tests for the Mitsubishi Comfort coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from mitsubishi_comfort import IndoorUnit

from homeassistant.components.mitsubishi_comfort.coordinator import (
    MitsubishiComfortCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


async def test_update_success(hass: HomeAssistant) -> None:
    """Test successful update returns the device."""
    device = MagicMock(spec=IndoorUnit)
    device.serial = "S001"
    device.name = "Test"
    device.update_status = AsyncMock(return_value=True)

    coordinator = MitsubishiComfortCoordinator(hass, device)
    result = await coordinator._async_update_data()

    assert result is device
    device.update_status.assert_awaited_once()


async def test_update_failure_raises(hass: HomeAssistant) -> None:
    """Test failed update raises UpdateFailed."""
    device = MagicMock(spec=IndoorUnit)
    device.serial = "S001"
    device.name = "Test"
    device.update_status = AsyncMock(return_value=False)

    coordinator = MitsubishiComfortCoordinator(hass, device)

    with pytest.raises(UpdateFailed, match="returned no data"):
        await coordinator._async_update_data()


async def test_update_exception_raises(hass: HomeAssistant) -> None:
    """Test exception during update raises UpdateFailed."""
    device = MagicMock(spec=IndoorUnit)
    device.serial = "S001"
    device.name = "Test"
    device.update_status = AsyncMock(side_effect=TimeoutError("timeout"))

    coordinator = MitsubishiComfortCoordinator(hass, device)

    with pytest.raises(UpdateFailed, match="Error communicating"):
        await coordinator._async_update_data()


async def test_coordinator_stores_device(hass: HomeAssistant) -> None:
    """Test coordinator stores device as data."""
    device = MagicMock(spec=IndoorUnit)
    device.serial = "S001"
    device.name = "Test"

    coordinator = MitsubishiComfortCoordinator(hass, device)

    assert coordinator.device is device
    assert coordinator.data is device


async def test_coordinator_name(hass: HomeAssistant) -> None:
    """Test coordinator name includes device serial."""
    device = MagicMock(spec=IndoorUnit)
    device.serial = "SERIAL001"
    device.name = "Living Room"

    coordinator = MitsubishiComfortCoordinator(hass, device)

    assert coordinator.name == "mitsubishi_comfort_SERIAL001"
