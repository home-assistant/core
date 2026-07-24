"""Tests for the PowerShades data update coordinator."""

from unittest.mock import AsyncMock, patch

from pyowershades import (
    OP_JOG_STOP,
    OP_SET_POSITION,
    PowerShadesConnection,
    PowerShadesTimeoutError,
    StatusReply,
    build_packet,
    build_set_position_payload,
)
import pytest

from homeassistant.components.powershades import coordinator as coordinator_module
from homeassistant.components.powershades.const import DOMAIN
from homeassistant.components.powershades.coordinator import PowerShadesCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import UpdateFailed

from .conftest import TEST_IP, TEST_NAME, TEST_SERIAL

from tests.common import MockConfigEntry


@pytest.fixture
def coordinator(hass: HomeAssistant, mock_connection):
    """A coordinator with a mocked connection, not yet started."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"ip": TEST_IP, "serial": TEST_SERIAL, "name": TEST_NAME, "model": 1},
        unique_id=str(TEST_SERIAL),
    )
    entry.add_to_hass(hass)
    connection = PowerShadesConnection(TEST_IP)
    return PowerShadesCoordinator(hass, entry, connection)


def test_data_from_status_no_target(coordinator) -> None:
    """Without a movement target, status is passed through unchanged."""
    data = coordinator._data_from_status(StatusReply(position=42, battery_mv=3700))
    assert data.position == 42
    assert data.battery_mv == 3700
    assert data.target_position is None
    assert data.battery_percentage is not None


def test_target_reached_clears_target(coordinator) -> None:
    """Arriving within tolerance of the target clears it."""
    coordinator._set_target(50)
    data = coordinator._data_from_status(StatusReply(position=51, battery_mv=3700))
    assert data.target_position is None


def test_unchanged_position_within_timeout_keeps_target(coordinator) -> None:
    """A position that hasn't changed yet is not immediately marked stuck."""
    times = [100.0, 100.0, 114.0]
    with patch.object(coordinator_module.time, "monotonic", side_effect=times):
        coordinator._set_target(0)
        data = coordinator._data_from_status(StatusReply(position=50, battery_mv=3700))
        assert data.target_position == 0

        data = coordinator._data_from_status(StatusReply(position=50, battery_mv=3700))
        assert data.target_position == 0


def test_stuck_position_clears_target_after_timeout(coordinator) -> None:
    """A position unchanged for STUCK_TIMEOUT seconds clears the target."""
    times = [100.0, 100.0, 116.0]
    with patch.object(coordinator_module.time, "monotonic", side_effect=times):
        coordinator._set_target(0)
        coordinator._data_from_status(StatusReply(position=50, battery_mv=3700))

        data = coordinator._data_from_status(StatusReply(position=50, battery_mv=3700))
        assert data.target_position is None


def test_continuous_movement_not_marked_stuck(coordinator) -> None:
    """A position that keeps changing never gets marked stuck."""
    times = [100.0, 100.0, 110.0, 120.0]
    with patch.object(coordinator_module.time, "monotonic", side_effect=times):
        coordinator._set_target(0)
        coordinator._data_from_status(StatusReply(position=50, battery_mv=3700))
        coordinator._data_from_status(StatusReply(position=40, battery_mv=3700))
        data = coordinator._data_from_status(StatusReply(position=30, battery_mv=3700))
        assert data.target_position == 0


def test_external_move_infers_opening_direction(coordinator) -> None:
    """A position increase with no active target is inferred as opening."""
    times = [100.0, 110.0]
    with patch.object(coordinator_module.time, "monotonic", side_effect=times):
        coordinator._data_from_status(StatusReply(position=50, battery_mv=3700))
        data = coordinator._data_from_status(StatusReply(position=60, battery_mv=3700))
        assert data.target_position == 100


def test_external_move_infers_closing_direction(coordinator) -> None:
    """A position decrease with no active target is inferred as closing."""
    times = [100.0, 110.0]
    with patch.object(coordinator_module.time, "monotonic", side_effect=times):
        coordinator._data_from_status(StatusReply(position=50, battery_mv=3700))
        data = coordinator._data_from_status(StatusReply(position=40, battery_mv=3700))
        assert data.target_position == 0


def test_external_move_clears_when_limit_reached(coordinator) -> None:
    """An inferred external move clears once it reaches the natural limit."""
    times = [100.0, 110.0, 115.0]
    with patch.object(coordinator_module.time, "monotonic", side_effect=times):
        coordinator._data_from_status(StatusReply(position=90, battery_mv=3700))
        data = coordinator._data_from_status(StatusReply(position=99, battery_mv=3700))
        assert data.target_position == 100

        data = coordinator._data_from_status(StatusReply(position=100, battery_mv=3700))
        assert data.target_position is None


def test_external_move_clears_after_stuck_timeout(coordinator) -> None:
    """An inferred external move that stalls is cleared after STUCK_TIMEOUT."""
    times = [100.0, 110.0, 126.0]
    with patch.object(coordinator_module.time, "monotonic", side_effect=times):
        coordinator._data_from_status(StatusReply(position=50, battery_mv=3700))
        data = coordinator._data_from_status(StatusReply(position=60, battery_mv=3700))
        assert data.target_position == 100

        data = coordinator._data_from_status(StatusReply(position=60, battery_mv=3700))
        assert data.target_position is None


def test_external_move_reversal_reinfers_direction(coordinator) -> None:
    """An external move that reverses direction re-infers the new target."""
    times = [100.0, 110.0, 115.0]
    with patch.object(coordinator_module.time, "monotonic", side_effect=times):
        coordinator._data_from_status(StatusReply(position=50, battery_mv=3700))
        data = coordinator._data_from_status(StatusReply(position=60, battery_mv=3700))
        assert data.target_position == 100

        data = coordinator._data_from_status(StatusReply(position=55, battery_mv=3700))
        assert data.target_position == 0


def test_ha_move_overridden_by_opposite_external_move(coordinator) -> None:
    """If the shade moves opposite to a HA-issued target, infer the new direction."""
    times = [100.0, 110.0, 115.0]
    with patch.object(coordinator_module.time, "monotonic", side_effect=times):
        coordinator._data_from_status(StatusReply(position=50, battery_mv=3700))
        coordinator._set_target(100)

        data = coordinator._data_from_status(StatusReply(position=40, battery_mv=3700))
        assert data.target_position == 0


async def test_async_set_position_sends_command(coordinator) -> None:
    """Setting a position sends a Set Position command and sets the target."""
    await coordinator.async_set_position(75)

    coordinator.connection.async_request.assert_any_call(
        OP_SET_POSITION, build_set_position_payload(75)
    )
    assert coordinator.data.target_position == 75


async def test_async_set_position_failure_clears_target(coordinator) -> None:
    """If the device doesn't ack the command, the target is cleared and raised."""

    async def fake_request(op, payload=b"", timeout=None, retries=None):
        raise PowerShadesTimeoutError("no reply")

    coordinator.connection.async_request = AsyncMock(side_effect=fake_request)

    with pytest.raises(HomeAssistantError) as exc_info:
        await coordinator.async_set_position(75)

    assert coordinator._target_position is None
    assert exc_info.value.translation_key == "command_not_acknowledged"


async def test_async_stop_clears_target(coordinator) -> None:
    """Stopping the shade clears the movement target."""
    coordinator._set_target(75)
    await coordinator.async_stop()

    coordinator.connection.async_request.assert_any_call(OP_JOG_STOP, b"")
    assert coordinator.data.target_position is None


async def test_async_update_data_polls_status(coordinator) -> None:
    """Polling fetches status and adjusts the update interval."""
    data = await coordinator._async_update_data()
    assert data.position == 50
    assert coordinator.update_interval.total_seconds() == 10


async def test_async_update_data_raises_on_timeout(coordinator) -> None:
    """A polling timeout raises UpdateFailed."""

    async def fake_request(op, payload=b"", timeout=None, retries=None):
        raise PowerShadesTimeoutError("no reply")

    coordinator.connection.async_request = AsyncMock(side_effect=fake_request)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_async_update_data_raises_on_malformed_reply(coordinator) -> None:
    """A reply that doesn't parse as a status reply raises UpdateFailed."""

    async def fake_request(op, payload=b"", timeout=None, retries=None):
        return build_packet(0x00)

    coordinator.connection.async_request = AsyncMock(side_effect=fake_request)

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()

    assert exc_info.value.translation_key == "update_malformed_reply"


def test_device_info_without_name_uses_ip(coordinator) -> None:
    """With no known shade name, the device name falls back to the IP address."""
    coordinator.device_name = None
    assert coordinator.device_info["name"] == f"PowerShade {coordinator.ip_address}"


def test_handle_status_push_updates_data(coordinator) -> None:
    """A pushed status packet updates the coordinator's data."""
    coordinator._handle_status_push(StatusReply(position=42, battery_mv=3700))
    assert coordinator.data.position == 42
