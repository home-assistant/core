"""Test the AirTouch 3 coordinator."""

import asyncio
from collections.abc import Coroutine
from enum import Enum
from typing import Any, cast
from unittest.mock import ANY, AsyncMock, Mock, call, patch

from pyairtouch3 import AirTouchError
from pyairtouch3.airtouch_aircon import Aircon
from pyairtouch3.airtouch_sensor import Sensor
from pyairtouch3.airtouch_zone import AirtouchZone
from pyairtouch3.enums import ZoneStatus
import pytest

from homeassistant.components.airtouch3.const import DOMAIN
from homeassistant.components.airtouch3.coordinator import (
    Airtouch3DataUpdateCoordinator,
    async_fetch_airtouch_data,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


class CommandType(Enum):
    """Test command enum."""

    SET_MODE = "set_mode"


def _zone(
    zone_id: int,
    name: str,
    desired_temperature: int,
    status: ZoneStatus,
    current_temperature: int | None = None,
) -> AirtouchZone:
    """Create a zone fixture."""
    zone = AirtouchZone(20)
    zone.id = zone_id
    zone.name = name
    zone.desired_temperature = desired_temperature
    zone.status = status
    if current_temperature is not None:
        sensor = Sensor()
        sensor.current_temperature = current_temperature
        sensor.is_available = True
        zone.sensor = sensor
    return zone


def _aircon() -> Aircon:
    """Create AirTouch data for coordinator tests."""
    aircon = Aircon(1)
    aircon.brand_id = 2
    aircon.status = True
    aircon.zones = [
        _zone(1, "Living", 20, ZoneStatus.ZONE_ON, 23),
        _zone(2, "Bedroom", 21, ZoneStatus.ZONE_OFF),
    ]
    return aircon


def _coordinator(hass: HomeAssistant) -> Airtouch3DataUpdateCoordinator:
    """Create a coordinator with data."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "1.1.1.1"})
    entry.add_to_hass(hass)
    coordinator = Airtouch3DataUpdateCoordinator(hass, entry, "1.1.1.1")
    coordinator.data = _aircon()
    return coordinator


def test_coordinator_does_not_start_command_worker_at_init(
    hass: HomeAssistant,
) -> None:
    """Test the long-running command worker is not created during setup."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "1.1.1.1"})
    entry.add_to_hass(hass)

    with (
        patch.object(hass, "async_create_task") as create_task,
        patch.object(hass, "async_create_background_task") as create_background_task,
    ):
        Airtouch3DataUpdateCoordinator(hass, entry, "1.1.1.1")

    create_task.assert_not_called()
    create_background_task.assert_not_called()


async def test_async_fetch_airtouch_data_success() -> None:
    """Test fetching AirTouch data delegates to pyairtouch3."""
    aircon = _aircon()
    fetch_aircon = AsyncMock(return_value=aircon)

    with patch(
        "homeassistant.components.airtouch3.coordinator.AirTouchClient"
    ) as client_class:
        client_class.return_value.fetch_aircon = fetch_aircon
        result = await async_fetch_airtouch_data("1.1.1.1")

    assert result is aircon
    client_class.assert_called_once_with("1.1.1.1", 8899, logger=ANY)
    fetch_aircon.assert_awaited_once()


async def test_async_fetch_airtouch_data_error_raises_update_failed() -> None:
    """Test pyairtouch3 errors are surfaced as update failures."""
    fetch_aircon = AsyncMock(side_effect=AirTouchError("bad response"))

    with patch(
        "homeassistant.components.airtouch3.coordinator.AirTouchClient"
    ) as client_class:
        client_class.return_value.fetch_aircon = fetch_aircon
        with pytest.raises(UpdateFailed):
            await async_fetch_airtouch_data("1.1.1.1")

    fetch_aircon.assert_awaited_once()


async def test_update_data_uses_parsed_response(hass: HomeAssistant) -> None:
    """Test coordinator refresh stores parsed AirTouch data."""
    coordinator = _coordinator(hass)
    parsed = _aircon()

    with patch(
        "homeassistant.components.airtouch3.coordinator.async_fetch_airtouch_data",
        AsyncMock(return_value=parsed),
    ):
        result = await coordinator._async_update_data()

    assert result is parsed


async def test_send_command_normalizes_command_key(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test command type enum values are normalized before dispatch."""
    coordinator = _coordinator(hass)
    ensure_worker = Mock()
    monkeypatch.setattr(coordinator, "_ensure_command_queue_worker", ensure_worker)

    await coordinator.send_command(cast(str, CommandType.SET_MODE), 1, 4)
    await coordinator.send_command(cast(str, 123), 1)

    assert coordinator._command_queue.get_nowait()[0] == "set_mode"
    assert coordinator._command_queue.empty()


@pytest.mark.parametrize(
    ("command_type", "target_id", "value"),
    [
        ("set_mode", 1, 4),
        ("set_fan_speed", 1, 3),
        ("set_group_temperature", 1, -1),
        ("toggle_zone", 1, None),
    ],
)
async def test_send_command_queues_command(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    command_type: str,
    target_id: int,
    value: int | None,
) -> None:
    """Test commands are converted to protocol messages and queued."""
    coordinator = _coordinator(hass)
    ensure_worker = Mock()
    monkeypatch.setattr(coordinator, "_ensure_command_queue_worker", ensure_worker)

    await coordinator.send_command(command_type, target_id, value)

    command_queue: asyncio.Queue[tuple[str, int, Any]] = coordinator._command_queue
    queued_type, queued_target, queued_value = command_queue.get_nowait()
    assert queued_type == command_type
    assert queued_target == target_id
    assert queued_value == value
    ensure_worker.assert_called_once()


@pytest.mark.parametrize(
    ("command_type", "initial_status", "expected_status"),
    [
        ("turn_on", False, True),
        ("turn_off", True, False),
    ],
)
async def test_send_command_queues_power_toggle(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    command_type: str,
    initial_status: bool,
    expected_status: bool,
) -> None:
    """Test AC power commands queue only when a toggle is required."""
    coordinator = _coordinator(hass)
    coordinator.data.status = initial_status
    ensure_worker = Mock()
    monkeypatch.setattr(coordinator, "_ensure_command_queue_worker", ensure_worker)

    await coordinator.send_command(command_type, 1)

    command_queue: asyncio.Queue[tuple[str, int, Any]] = coordinator._command_queue
    assert command_queue.get_nowait()[0:2] == (command_type, 1)
    assert coordinator.data.status is expected_status
    ensure_worker.assert_called_once()


@pytest.mark.parametrize(
    ("command_type", "initial_status"),
    [
        ("turn_on", True),
        ("turn_off", False),
        ("unknown", True),
    ],
)
async def test_send_command_skips_unneeded_or_unknown_commands(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    command_type: str,
    initial_status: bool,
) -> None:
    """Test no command is queued when no protocol message is needed."""
    coordinator = _coordinator(hass)
    coordinator.data.status = initial_status
    ensure_worker = Mock()
    monkeypatch.setattr(coordinator, "_ensure_command_queue_worker", ensure_worker)

    await coordinator.send_command(command_type, 1)

    command_queue: asyncio.Queue[tuple[str, int, Any]] = coordinator._command_queue
    assert command_queue.empty()
    ensure_worker.assert_not_called()


def test_ensure_command_queue_worker_starts_once(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test the command queue worker is only started when needed."""
    coordinator = _coordinator(hass)
    running_task = Mock()
    running_task.done.return_value = False
    coordinator._command_queue_task = running_task
    create_background_task = Mock()
    monkeypatch.setattr(
        coordinator._entry, "async_create_background_task", create_background_task
    )

    coordinator._ensure_command_queue_worker()

    create_background_task.assert_not_called()

    coordinator._command_queue_task = None

    def _create_background_task(
        _hass: HomeAssistant, coro: Coroutine[Any, Any, None], name: str
    ) -> Mock:
        """Close the worker coroutine and return a fake task."""
        coro.close()
        return Mock(name=name)

    monkeypatch.setattr(
        coordinator._entry, "async_create_background_task", _create_background_task
    )

    coordinator._ensure_command_queue_worker()

    assert coordinator._command_queue_task is not None


async def test_command_queue_worker_sends_queued_command(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test the command queue worker sends queued commands."""
    coordinator = _coordinator(hass)
    send_queued_command = AsyncMock()
    monkeypatch.setattr(coordinator, "_async_send_queued_command", send_queued_command)
    coordinator._command_queue_interval = 0
    await coordinator._command_queue.put(("toggle_zone", 1, None))

    worker = asyncio.create_task(coordinator._async_command_queue_worker())
    await coordinator._command_queue.join()
    worker.cancel()
    await worker

    send_queued_command.assert_awaited_once_with("toggle_zone", 1, None)
    assert coordinator._command_queue.empty()


async def test_command_queue_worker_stops_when_cancelled_while_waiting(
    hass: HomeAssistant,
) -> None:
    """Test the command queue worker exits cleanly while waiting for commands."""
    coordinator = _coordinator(hass)
    worker = asyncio.create_task(coordinator._async_command_queue_worker())

    await asyncio.sleep(0)
    worker.cancel()
    await worker

    assert worker.done()


async def test_shutdown_cancels_worker(hass: HomeAssistant) -> None:
    """Test shutdown cancels the command worker."""
    coordinator = _coordinator(hass)
    task = asyncio.create_task(asyncio.sleep(60))
    coordinator._command_queue_task = task

    await coordinator._async_shutdown(None)

    assert task.cancelled()


@pytest.mark.parametrize(
    ("command_type", "target_id", "value", "method_name", "expected_args"),
    [
        ("set_mode", 1, 4, "set_mode", (1, 2, 4)),
        ("set_fan_speed", 1, 3, "set_fan_speed", (1, 2, 3)),
        ("set_group_temperature", 1, -1, "adjust_zone_temperature", (1, -1)),
        ("turn_on", 1, None, "toggle_ac_power", (1,)),
        ("turn_off", 1, None, "toggle_ac_power", (1,)),
        ("toggle_zone", 1, None, "toggle_zone", (1,)),
    ],
)
async def test_send_queued_command_delegates_to_pyairtouch3_client(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    command_type: str,
    target_id: int,
    value: int | None,
    method_name: str,
    expected_args: tuple[Any, ...],
) -> None:
    """Test queued command delivery delegates to the pyairtouch3 client."""
    coordinator = _coordinator(hass)
    method = AsyncMock()
    monkeypatch.setattr(coordinator._client, method_name, method)

    await coordinator._async_send_queued_command(command_type, target_id, value)

    method.assert_awaited_once_with(*expected_args)


async def test_send_queued_command_handles_write_error(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test queued command delivery handles pyairtouch3 write errors."""
    coordinator = _coordinator(hass)
    toggle_zone = AsyncMock(side_effect=AirTouchError("closed"))
    monkeypatch.setattr(coordinator._client, "toggle_zone", toggle_zone)

    await coordinator._async_send_queued_command("toggle_zone", 1, None)

    toggle_zone.assert_awaited_once_with(1)


async def test_adjust_temperature_sends_step_commands(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test coordinator temperature adjustment sends one command per step."""
    coordinator = _coordinator(hass)
    send_command = AsyncMock()
    monkeypatch.setattr(coordinator, "send_command", send_command)

    with patch(
        "homeassistant.components.airtouch3.coordinator.asyncio.sleep", AsyncMock()
    ) as sleep:
        await coordinator.adjust_temperature(1, 22)

    assert send_command.mock_calls == [
        call("set_group_temperature", 1, 1),
        call("set_group_temperature", 1, 1),
    ]
    assert sleep.await_count == 2


async def test_adjust_temperature_skips_missing_target(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test coordinator temperature adjustment skips unknown zones."""
    coordinator = _coordinator(hass)
    send_command = AsyncMock()
    monkeypatch.setattr(coordinator, "send_command", send_command)

    await coordinator.adjust_temperature(99, 22)

    send_command.assert_not_called()
