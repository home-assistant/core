"""Tests for the Arcam FMJ coordinator."""

from unittest.mock import Mock

from arcam.fmj import ConnectionFailed
import pytest

from homeassistant.components.arcam_fmj.coordinator import ArcamFmjCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


async def test_initial_update_connection_failed(
    hass: HomeAssistant, coordinator_1: ArcamFmjCoordinator, state_1: Mock
) -> None:
    """Test _async_initial_update marks unavailable on ConnectionFailed."""
    coordinator_1.last_update_success = True
    state_1.update.side_effect = ConnectionFailed
    await coordinator_1._async_initial_update()
    state_1.update.assert_called_once()
    assert coordinator_1.last_update_success is False


async def test_initial_update_success(
    hass: HomeAssistant, coordinator_1: ArcamFmjCoordinator, state_1: Mock
) -> None:
    """Test _async_initial_update marks available and sets data on success."""
    coordinator_1.last_update_success = False
    await coordinator_1._async_initial_update()
    state_1.update.assert_called_once()
    assert coordinator_1.last_update_success is True
    assert coordinator_1.data is state_1


async def test_async_notify_data_updated(
    hass: HomeAssistant, coordinator_1: ArcamFmjCoordinator
) -> None:
    """Test async_notify_data_updated sets data on the coordinator."""
    callback_called = False

    def listener() -> None:
        nonlocal callback_called
        callback_called = True

    coordinator_1.async_add_listener(listener)
    coordinator_1.async_notify_data_updated()
    assert callback_called


async def test_async_notify_connected(
    hass: HomeAssistant, coordinator_1: ArcamFmjCoordinator, state_1: Mock
) -> None:
    """Test async_notify_connected triggers initial update."""
    coordinator_1.async_notify_connected()
    await hass.async_block_till_done()
    assert coordinator_1.last_update_success is True
    state_1.update.assert_called_once()
    assert coordinator_1.data is state_1


async def test_async_update_data_connection_failed(
    hass: HomeAssistant, coordinator_1: ArcamFmjCoordinator, state_1: Mock
) -> None:
    """Test _async_update_data raises UpdateFailed on ConnectionFailed."""
    state_1.update.side_effect = ConnectionFailed
    with pytest.raises(UpdateFailed):
        await coordinator_1._async_update_data()
