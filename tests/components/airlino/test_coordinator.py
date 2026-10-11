"""Tests for the AirLino data update coordinator."""

import logging
from unittest.mock import AsyncMock, MagicMock

from airlino_api import AirlinoApiConnectionError, AirlinoApiError
import pytest

from homeassistant.components.airlino.const import DOMAIN
from homeassistant.components.airlino.coordinator import AirlinoDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


@pytest.fixture
def coordinator(
    hass: HomeAssistant,
) -> tuple[AirlinoDataUpdateCoordinator, MagicMock]:
    """Create a coordinator and mocked AirLino API."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="AirLino",
        data={"host": "192.0.2.1", "setup_verified": False},
        unique_id="00:11:22:33:44:55",
    )
    api = MagicMock()
    api.async_get_device_info = AsyncMock(
        return_value={"devicename": "Living room", "model": "AirLino"}
    )
    api.async_get_player_status = AsyncMock(return_value={"state": "stopped"})
    api.async_get_master_volume = AsyncMock(return_value=50)
    api.async_get_sender_status = AsyncMock(return_value={"enabled": False})
    api.async_get_receiver_state = AsyncMock(return_value={"sender": None})
    return AirlinoDataUpdateCoordinator(hass, entry, api), api


async def test_update_returns_current_device_data(
    coordinator: tuple[AirlinoDataUpdateCoordinator, MagicMock],
) -> None:
    """Check that a successful update returns core and Songcast data."""
    update_coordinator, api = coordinator

    data = await update_coordinator._async_update_data()

    assert data["online"] is True
    assert data["device"] == {"devicename": "Living room", "model": "AirLino"}
    assert data["player"] == {"state": "stopped"}
    assert data["volume"] == 50
    assert data["sender"] == {"enabled": False}
    assert data["receiver"] == {"sender": None}
    api.async_get_device_info.assert_awaited_once()
    api.async_get_player_status.assert_awaited_once()
    api.async_get_master_volume.assert_awaited_once()


async def test_songcast_failure_preserves_previous_state(
    coordinator: tuple[AirlinoDataUpdateCoordinator, MagicMock],
) -> None:
    """Keep the last known group status after an optional call fails."""
    update_coordinator, api = coordinator
    previous_sender = {"enabled": True, "uuid": "sender-uuid"}
    previous_receiver = {"sender": "sender-uuid"}
    update_coordinator.data = {
        "online": True,
        "sender": previous_sender,
        "receiver": previous_receiver,
    }
    api.async_get_sender_status.side_effect = AirlinoApiError("temporary error")

    data = await update_coordinator._async_update_data()

    assert data["sender"] == previous_sender
    assert data["receiver"] == previous_receiver
    api.async_get_receiver_state.assert_not_awaited()


async def test_receiver_status_failure_preserves_previous_state(
    coordinator: tuple[AirlinoDataUpdateCoordinator, MagicMock],
) -> None:
    """Preserve successful sender data when the receiver query fails."""
    update_coordinator, api = coordinator
    previous_sender = {"enabled": True, "uuid": "sender-uuid"}
    previous_receiver = {"sender": "sender-uuid"}
    update_coordinator.data = {
        "online": True,
        "sender": previous_sender,
        "receiver": previous_receiver,
    }
    api.async_get_sender_status.return_value = {"enabled": False}
    api.async_get_receiver_state.side_effect = AirlinoApiConnectionError("timeout")

    data = await update_coordinator._async_update_data()

    assert data["sender"] == {"enabled": False}
    assert data["receiver"] == previous_receiver


async def test_recovery_after_offline_logs_and_returns_online(
    coordinator: tuple[AirlinoDataUpdateCoordinator, MagicMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Report an online device after a prior offline update."""
    update_coordinator, _ = coordinator
    update_coordinator.data = {"online": False}
    caplog.set_level(logging.INFO)

    data = await update_coordinator._async_update_data()

    assert data["online"] is True
    assert "AirLino is available again" in caplog.text


async def test_device_info_is_refetched_after_offline(
    coordinator: tuple[AirlinoDataUpdateCoordinator, MagicMock],
) -> None:
    """Fetch device information again after a previous offline result."""
    update_coordinator, api = coordinator
    update_coordinator._device_info = {"devicename": "Old name"}
    update_coordinator._refetch_device_info = True

    data = await update_coordinator._async_update_data()

    assert data["device"] == {"devicename": "Living room", "model": "AirLino"}
    api.async_get_device_info.assert_awaited_once()


async def test_initial_connection_failure_fails_update(
    coordinator: tuple[AirlinoDataUpdateCoordinator, MagicMock],
) -> None:
    """Fail the initial update for an unverified config entry."""
    update_coordinator, api = coordinator
    api.async_get_device_info.side_effect = AirlinoApiConnectionError("offline")

    with pytest.raises(UpdateFailed):
        await update_coordinator._async_update_data()

    api.async_get_player_status.assert_not_awaited()


async def test_verified_entry_reports_offline_after_restart(
    coordinator: tuple[AirlinoDataUpdateCoordinator, MagicMock],
) -> None:
    """Allow an established entry to load offline after a restart."""
    update_coordinator, api = coordinator
    update_coordinator._setup_verified = True
    api.async_get_device_info.side_effect = AirlinoApiConnectionError("offline")

    data = await update_coordinator._async_update_data()

    assert data == {"online": False, "device": None}
    api.async_get_player_status.assert_not_awaited()


async def test_connection_failure_reports_offline(
    coordinator: tuple[AirlinoDataUpdateCoordinator, MagicMock],
) -> None:
    """Report an unreachable device as offline after a successful update."""
    update_coordinator, api = coordinator
    update_coordinator._setup_verified = True
    update_coordinator.data = {"online": True, "device": {"model": "AirLino"}}
    api.async_get_device_info.side_effect = AirlinoApiConnectionError("offline")

    data = await update_coordinator._async_update_data()

    assert data == {"online": False, "device": update_coordinator._device_info}
    api.async_get_player_status.assert_not_awaited()


async def test_unexpected_failure_becomes_update_failed(
    coordinator: tuple[AirlinoDataUpdateCoordinator, MagicMock],
) -> None:
    """Translate unexpected polling errors into UpdateFailed."""
    update_coordinator, api = coordinator
    api.async_get_device_info.side_effect = RuntimeError("unexpected")

    with pytest.raises(UpdateFailed):
        await update_coordinator._async_update_data()
