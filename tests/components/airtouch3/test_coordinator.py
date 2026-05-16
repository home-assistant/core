"""Test the AirTouch 3 coordinator."""

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from enum import Enum
from typing import Any, cast
from unittest.mock import AsyncMock, Mock, call, patch

import pytest

from homeassistant.components.airtouch3.comms.airtouch_aircon import Aircon
from homeassistant.components.airtouch3.comms.airtouch_sensor import Sensor
from homeassistant.components.airtouch3.comms.airtouch_zone import AirtouchZone
from homeassistant.components.airtouch3.comms.enums import ZoneStatus
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


class FakeStreamReader:
    """Fake stream reader for AirTouch socket tests."""

    def __init__(self, data: bytes) -> None:
        """Initialize the fake reader."""
        self._data = data

    async def read(self, _limit: int) -> bytes:
        """Return the configured data."""
        return self._data


class FakeStreamWriter:
    """Fake stream writer for AirTouch socket tests."""

    def __init__(self) -> None:
        """Initialize the fake writer."""
        self.written_data: bytearray | None = None
        self.closed = False
        self.drain = AsyncMock()
        self.wait_closed = AsyncMock()

    def write(self, data: bytearray) -> None:
        """Store written data."""
        self.written_data = data

    def close(self) -> None:
        """Mark the writer closed."""
        self.closed = True


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
    aircon.group_target_temperatures = {1: 20, 2: 21}
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
    """Test fetching AirTouch data writes the init message and parses the response."""
    aircon = _aircon()
    reader = FakeStreamReader(b"\x00" * 520)
    writer = FakeStreamWriter()

    with (
        patch(
            "homeassistant.components.airtouch3.coordinator.asyncio.open_connection",
            AsyncMock(return_value=(reader, writer)),
        ) as open_connection,
        patch(
            "homeassistant.components.airtouch3.coordinator.MessageResponseParser"
        ) as parser,
    ):
        parser.return_value.parse.return_value = aircon
        result = await async_fetch_airtouch_data("1.1.1.1")

    assert result is aircon
    open_connection.assert_awaited_once_with("1.1.1.1", 8899)
    assert writer.written_data == bytearray([85, 1, 12, 0, 0, 0, 0, 0, 0, 0, 0, 0, 98])
    writer.drain.assert_awaited_once()
    assert writer.closed is True
    writer.wait_closed.assert_awaited_once()


async def test_async_fetch_airtouch_data_short_response_raises() -> None:
    """Test short AirTouch responses raise UpdateFailed."""
    reader = FakeStreamReader(b"\x00")
    writer = FakeStreamWriter()

    with (
        patch(
            "homeassistant.components.airtouch3.coordinator.asyncio.open_connection",
            AsyncMock(return_value=(reader, writer)),
        ),
        pytest.raises(UpdateFailed),
    ):
        await async_fetch_airtouch_data("1.1.1.1")

    assert writer.closed is True


async def test_async_fetch_airtouch_data_parse_error_raises() -> None:
    """Test parse errors are surfaced as update failures."""
    reader = FakeStreamReader(b"\x00" * 520)
    writer = FakeStreamWriter()

    with (
        patch(
            "homeassistant.components.airtouch3.coordinator.asyncio.open_connection",
            AsyncMock(return_value=(reader, writer)),
        ),
        patch(
            "homeassistant.components.airtouch3.coordinator.MessageResponseParser"
        ) as parser,
    ):
        parser.return_value.parse.side_effect = ValueError("bad response")
        with pytest.raises(UpdateFailed):
            await async_fetch_airtouch_data("1.1.1.1")

    assert writer.closed is True


async def test_connect_to_airtouch_success(hass: HomeAssistant) -> None:
    """Test connecting to AirTouch stores socket handles."""
    coordinator = _coordinator(hass)
    reader = FakeStreamReader(b"")
    writer = FakeStreamWriter()

    with patch(
        "homeassistant.components.airtouch3.coordinator.asyncio.open_connection",
        AsyncMock(return_value=(reader, writer)),
    ):
        await coordinator.connect_to_airtouch()

    assert coordinator.connected is True
    assert coordinator.socket_reader is not None
    assert coordinator.socket_writer is not None


async def test_connect_to_airtouch_failure(hass: HomeAssistant) -> None:
    """Test connection errors are surfaced as update failures."""
    coordinator = _coordinator(hass)

    with (
        patch(
            "homeassistant.components.airtouch3.coordinator.asyncio.open_connection",
            AsyncMock(side_effect=OSError("no route")),
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator.connect_to_airtouch()

    assert coordinator.connected is False


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
    assert result.groups == [
        {"id": 1, "name": "Living"},
        {"id": 2, "name": "Bedroom"},
    ]
    assert result.group_temperatures == {1: 23}
    assert result.group_target_temperatures == {1: 20, 2: 21}
    assert result.group_power_states == {1: True, 2: False}


async def test_send_command_normalizes_command_key(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test command type enum values are normalized before dispatch."""
    coordinator = _coordinator(hass)
    ensure_worker = Mock()
    monkeypatch.setattr(coordinator, "_ensure_command_queue_worker", ensure_worker)

    await coordinator.send_command(cast(str, CommandType.SET_MODE), 1, 4)
    await coordinator.send_command(cast(str, 123), 1)

    assert coordinator._command_queue.get_nowait()[1] == "set_mode"
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

    command_queue: asyncio.Queue[tuple[bytearray, str, int, Any]] = (
        coordinator._command_queue
    )
    queued_msg, queued_type, queued_target, queued_value = command_queue.get_nowait()
    assert len(queued_msg) == 13
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

    command_queue: asyncio.Queue[tuple[bytearray, str, int, Any]] = (
        coordinator._command_queue
    )
    assert command_queue.get_nowait()[1:3] == (command_type, 1)
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

    command_queue: asyncio.Queue[tuple[bytearray, str, int, Any]] = (
        coordinator._command_queue
    )
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
    await coordinator._command_queue.put(
        (bytearray(b"command"), "toggle_zone", 1, None)
    )

    worker = asyncio.create_task(coordinator._async_command_queue_worker())
    await coordinator._command_queue.join()
    worker.cancel()
    await worker

    send_queued_command.assert_awaited_once_with(
        bytearray(b"command"), "toggle_zone", 1, None
    )
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


async def test_shutdown_cancels_worker_and_closes_socket(hass: HomeAssistant) -> None:
    """Test shutdown cancels the command worker and closes the socket."""
    coordinator = _coordinator(hass)
    writer = FakeStreamWriter()
    task = asyncio.create_task(asyncio.sleep(60))
    coordinator.connected = True
    coordinator.socket_writer = cast(asyncio.StreamWriter, writer)
    coordinator._command_queue_task = task

    await coordinator._async_shutdown(None)

    assert task.cancelled()
    assert writer.closed is True
    writer.wait_closed.assert_awaited_once()
    assert coordinator.connected is False


async def test_send_queued_command_writes_and_closes_socket(
    hass: HomeAssistant,
) -> None:
    """Test queued command delivery writes to the AirTouch socket."""
    coordinator = _coordinator(hass)
    writer = FakeStreamWriter()
    coordinator.connected = True
    coordinator.socket_writer = cast(asyncio.StreamWriter, writer)
    send_queued_command: Callable[[bytearray, str, int, Any], Awaitable[None]] = (
        coordinator._async_send_queued_command
    )

    await send_queued_command(bytearray(b"command"), "toggle_zone", 1, None)

    assert writer.written_data == bytearray(b"command")
    writer.drain.assert_awaited_once()
    assert writer.closed is True
    writer.wait_closed.assert_awaited_once()
    assert coordinator.connected is False


async def test_send_queued_command_handles_missing_socket(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test queued command delivery handles a failed connection."""
    coordinator = _coordinator(hass)
    connect = AsyncMock()
    monkeypatch.setattr(coordinator, "connect_to_airtouch", connect)
    send_queued_command: Callable[[bytearray, str, int, Any], Awaitable[None]] = (
        coordinator._async_send_queued_command
    )

    await send_queued_command(bytearray(b"command"), "toggle_zone", 1, None)

    connect.assert_awaited_once()
    assert coordinator.connected is False


async def test_send_queued_command_handles_write_error(
    hass: HomeAssistant,
) -> None:
    """Test queued command delivery handles socket write errors."""
    coordinator = _coordinator(hass)
    writer = FakeStreamWriter()
    writer.drain.side_effect = OSError("closed")
    coordinator.connected = True
    coordinator.socket_writer = cast(asyncio.StreamWriter, writer)
    send_queued_command: Callable[[bytearray, str, int, Any], Awaitable[None]] = (
        coordinator._async_send_queued_command
    )

    await send_queued_command(bytearray(b"command"), "toggle_zone", 1, None)

    assert coordinator.connected is False
    assert writer.closed is True


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
