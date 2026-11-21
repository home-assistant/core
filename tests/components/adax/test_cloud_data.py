"""Test how the Adax cloud coordinator handles new, missing and commanded data."""

import asyncio
from collections.abc import Coroutine, Generator
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.adax.const import SCAN_INTERVAL
from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    ClimateEntityStateAttribute,
    ClimateService,
    ClimateServiceArgument,
    HVACMode,
)
from homeassistant.const import STATE_UNAVAILABLE, Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from . import setup_integration
from .conftest import CLOUD_DEVICE_DATA

from tests.test_setup import FrozenDateTimeFactory

ENTITY_ID = "climate.room_1"


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.adax.PLATFORMS", [Platform.CLIMATE]):
        yield


def _rooms(**changes: Any) -> list[dict[str, Any]]:
    """Return a new room list, as the client builds when a fetch gets data."""
    return [{**CLOUD_DEVICE_DATA[0], **changes}]


def _make_client(rooms: list[dict[str, Any]]) -> MagicMock:
    """Make a client that behaves like adax 0.4.0.

    fetch_rooms_info() returns None, and get_rooms() returns the client's room
    list. A test replaces that list to simulate a fetch that got data. A
    command the cloud accepts changes the client's room in place.
    """
    client = MagicMock()
    client.rooms = rooms
    client.sent_at = []
    client.accept_commands = True
    client.fetch_rooms_info = AsyncMock(return_value=None)
    client.get_rooms = AsyncMock(side_effect=lambda: client.rooms)

    async def _set(room_id: str, temperature: float, heating_enabled: bool) -> None:
        client.sent_at.append(dt_util.utcnow())
        if not client.accept_commands:
            return
        for room in client.rooms:
            if room["id"] == room_id:
                room["targetTemperature"] = int(temperature * 100) / 100
                room["heatingEnabled"] = heating_enabled

    client.set_room_target_temperature = AsyncMock(side_effect=_set)
    return client


@pytest.fixture
def start_rooms() -> list[dict[str, Any]]:
    """Return the rooms a new client gets on its first fetch."""
    return _rooms()


@pytest.fixture
def clients(start_rooms: list[dict[str, Any]]) -> Generator[list[MagicMock]]:
    """Patch the Adax cloud client; every client created is added to the list."""
    created: list[MagicMock] = []

    def _new_client(*args: Any, **kwargs: Any) -> MagicMock:
        created.append(_make_client([dict(room) for room in start_rooms]))
        return created[-1]

    with patch(
        "homeassistant.components.adax.coordinator.Adax", side_effect=_new_client
    ):
        yield created


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float
) -> None:
    """Move time on and let what is due run."""
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Move on to the next scheduled poll."""
    await _tick(hass, freezer, SCAN_INTERVAL.total_seconds())


def _state(hass: HomeAssistant) -> str:
    state = hass.states.get(ENTITY_ID)
    assert state
    return state.state


def _attr(hass: HomeAssistant, attr: str) -> Any:
    state = hass.states.get(ENTITY_ID)
    assert state
    return state.attributes[attr]


async def _set_hvac_mode(hass: HomeAssistant, mode: HVACMode) -> None:
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_HVAC_MODE,
        {TargetKey.ENTITY_ID: ENTITY_ID, ClimateServiceArgument.HVAC_MODE: mode},
        blocking=True,
    )


async def _run(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, coro: Coroutine[Any, Any, Any]
) -> Any:
    """Run a service call, moving time on while it waits for the client."""
    task = asyncio.create_task(coro)
    for _ in range(20):
        for _ in range(10):
            await asyncio.sleep(0)
        if task.done():
            break
        freezer.tick(timedelta(seconds=10))
        async_fire_time_changed(hass)
    return await task


async def test_no_new_data(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_cloud_config_entry: MockConfigEntry,
    clients: list[MagicMock],
) -> None:
    """Test polls without new data keep the last data for 10 minutes only."""
    await setup_integration(hass, mock_cloud_config_entry)
    assert _state(hass) == HVACMode.HEAT

    # The cloud changes, but the client's fetches get nothing.
    for _ in range(9):
        await _poll(hass, freezer)
        assert _state(hass) == HVACMode.HEAT
        assert len(clients) == 1

    # 10 minutes without new data: unavailable, and a new client.
    await _poll(hass, freezer)
    assert _state(hass) == STATE_UNAVAILABLE
    assert len(clients) == 2
    assert mock_cloud_config_entry.runtime_data.adax_data_handler is clients[1]

    # The new client gets the cloud's data; the old one is not used again.
    clients[1].rooms = _rooms(heatingEnabled=False, temperature=17)
    await _poll(hass, freezer)
    assert _state(hass) == HVACMode.OFF
    assert _attr(hass, ClimateEntityStateAttribute.CURRENT_TEMPERATURE) == 17
    assert clients[0].fetch_rooms_info.call_count == 11
    assert clients[1].fetch_rooms_info.call_count == 1


async def test_no_data_from_new_client(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_cloud_config_entry: MockConfigEntry,
    clients: list[MagicMock],
) -> None:
    """Test a new client is created at most every 10 minutes."""
    await setup_integration(hass, mock_cloud_config_entry)
    for _ in range(10):
        await _poll(hass, freezer)
    assert len(clients) == 2

    # The new client has no rooms until a fetch works.
    clients[1].rooms = []
    for _ in range(9):
        await _poll(hass, freezer)
        assert _state(hass) == STATE_UNAVAILABLE
        assert len(clients) == 2
    await _poll(hass, freezer)
    assert len(clients) == 3


async def test_new_data_with_the_same_values(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_cloud_config_entry: MockConfigEntry,
    clients: list[MagicMock],
) -> None:
    """Test new data with unchanged values counts as new data."""
    await setup_integration(hass, mock_cloud_config_entry)
    for _ in range(15):
        clients[0].rooms = _rooms()
        await _poll(hass, freezer)
        assert _state(hass) == HVACMode.HEAT
    assert len(clients) == 1


async def test_new_data_then_none(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_cloud_config_entry: MockConfigEntry,
    clients: list[MagicMock],
) -> None:
    """Test the 10 minutes run from the last new data, not from setup."""
    await setup_integration(hass, mock_cloud_config_entry)
    for minute in range(15):
        clients[0].rooms = _rooms(temperature=10 + minute)
        await _poll(hass, freezer)
        assert _attr(hass, ClimateEntityStateAttribute.CURRENT_TEMPERATURE) == (
            10 + minute
        )

    for _ in range(9):
        await _poll(hass, freezer)
        assert _state(hass) == HVACMode.HEAT
        assert _attr(hass, ClimateEntityStateAttribute.CURRENT_TEMPERATURE) == 24
    await _poll(hass, freezer)
    assert _state(hass) == STATE_UNAVAILABLE


async def test_client_changes_are_not_cloud_data(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_cloud_config_entry: MockConfigEntry,
    clients: list[MagicMock],
) -> None:
    """Test changes the client makes to its own rooms are not shown."""
    await setup_integration(hass, mock_cloud_config_entry)

    clients[0].rooms[0]["heatingEnabled"] = False
    clients[0].rooms[0]["temperature"] = 30
    await _poll(hass, freezer)
    assert _state(hass) == HVACMode.HEAT
    assert _attr(hass, ClimateEntityStateAttribute.CURRENT_TEMPERATURE) == 15


async def test_command_shown_until_new_data(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_cloud_config_entry: MockConfigEntry,
    clients: list[MagicMock],
) -> None:
    """Test a command shows at once, and new data from the cloud wins after."""
    await setup_integration(hass, mock_cloud_config_entry)

    await _run(hass, freezer, _set_hvac_mode(hass, HVACMode.OFF))
    clients[0].set_room_target_temperature.assert_called_once_with("1", 5, False)
    assert _state(hass) == HVACMode.OFF
    assert _attr(hass, ClimateEntityStateAttribute.TARGET_TEMPERATURE) == 5

    # No new data: keep showing the command.
    await _poll(hass, freezer)
    assert _state(hass) == HVACMode.OFF

    # New data says the heater is still on: show that.
    clients[0].rooms = _rooms(targetTemperature=21.5)
    await _poll(hass, freezer)
    assert _state(hass) == HVACMode.HEAT
    assert _attr(hass, ClimateEntityStateAttribute.TARGET_TEMPERATURE) == 21.5


async def test_command_waits_for_the_client(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_cloud_config_entry: MockConfigEntry,
    clients: list[MagicMock],
) -> None:
    """Test a command is sent only once the client allows a request."""
    await setup_integration(hass, mock_cloud_config_entry)
    setup_done = dt_util.utcnow()

    await _run(hass, freezer, _set_hvac_mode(hass, HVACMode.OFF))
    assert clients[0].sent_at[0] - setup_done >= timedelta(seconds=31)


async def test_set_hvac_mode_heat(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_cloud_config_entry: MockConfigEntry,
    clients: list[MagicMock],
) -> None:
    """Test turning a heater on sends its last target temperature."""
    await setup_integration(hass, mock_cloud_config_entry)
    clients[0].rooms = _rooms(heatingEnabled=False, targetTemperature=19)
    await _poll(hass, freezer)
    assert _state(hass) == HVACMode.OFF

    await _run(hass, freezer, _set_hvac_mode(hass, HVACMode.HEAT))
    clients[0].set_room_target_temperature.assert_called_once_with("1", 19, True)
    assert _state(hass) == HVACMode.HEAT
    assert _attr(hass, ClimateEntityStateAttribute.TARGET_TEMPERATURE) == 19


async def test_set_temperature(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_cloud_config_entry: MockConfigEntry,
    clients: list[MagicMock],
) -> None:
    """Test setting the temperature turns heating on and shows the target."""
    await setup_integration(hass, mock_cloud_config_entry)

    await _run(
        hass,
        freezer,
        hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_TEMPERATURE,
            {TargetKey.ENTITY_ID: ENTITY_ID, ClimateServiceArgument.TEMPERATURE: 18},
            blocking=True,
        ),
    )
    clients[0].set_room_target_temperature.assert_called_once_with("1", 18, True)
    assert _state(hass) == HVACMode.HEAT
    assert _attr(hass, ClimateEntityStateAttribute.TARGET_TEMPERATURE) == 18


async def test_command_not_accepted(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_cloud_config_entry: MockConfigEntry,
    clients: list[MagicMock],
) -> None:
    """Test a command the cloud refuses raises and is not shown."""
    await setup_integration(hass, mock_cloud_config_entry)
    clients[0].accept_commands = False

    with pytest.raises(HomeAssistantError) as err:
        await _run(hass, freezer, _set_hvac_mode(hass, HVACMode.OFF))
    assert err.value.translation_key == "command_failed"
    assert _state(hass) == HVACMode.HEAT


async def test_command_timeout(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_cloud_config_entry: MockConfigEntry,
    clients: list[MagicMock],
) -> None:
    """Test a command the client never finishes raises instead of hanging."""
    await setup_integration(hass, mock_cloud_config_entry)
    never = asyncio.Event()

    async def _hang(*args: Any) -> None:
        await never.wait()

    clients[0].set_room_target_temperature.side_effect = _hang

    with (
        patch("homeassistant.components.adax.coordinator.COMMAND_TIMEOUT", 60),
        pytest.raises(HomeAssistantError) as err,
    ):
        await _run(hass, freezer, _set_hvac_mode(hass, HVACMode.OFF))
    assert err.value.translation_key == "command_timeout"
    assert _state(hass) == HVACMode.HEAT
    # The old client may still send the command later, so it is replaced.
    assert len(clients) == 2
    assert mock_cloud_config_entry.runtime_data.adax_data_handler is clients[1]


async def test_newer_command_for_the_same_room(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_cloud_config_entry: MockConfigEntry,
    clients: list[MagicMock],
) -> None:
    """Test a command replaced before it was sent does not raise."""
    await setup_integration(hass, mock_cloud_config_entry)

    async def _both() -> None:
        await asyncio.gather(
            _set_hvac_mode(hass, HVACMode.OFF), _set_hvac_mode(hass, HVACMode.HEAT)
        )

    await _run(hass, freezer, _both())
    clients[0].set_room_target_temperature.assert_called_once_with("1", 20, True)
    assert _state(hass) == HVACMode.HEAT


@pytest.mark.parametrize(
    "start_rooms",
    [
        [
            {**CLOUD_DEVICE_DATA[0]},
            {**CLOUD_DEVICE_DATA[0], "id": "2", "name": "Room 2"},
        ]
    ],
)
async def test_commands_sent_together(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_cloud_config_entry: MockConfigEntry,
    clients: list[MagicMock],
) -> None:
    """Test commands for several rooms go to the client together."""
    await setup_integration(hass, mock_cloud_config_entry)

    await _run(
        hass,
        freezer,
        hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_HVAC_MODE,
            {
                TargetKey.ENTITY_ID: [ENTITY_ID, "climate.room_2"],
                ClimateServiceArgument.HVAC_MODE: HVACMode.OFF,
            },
            blocking=True,
        ),
    )
    assert clients[0].set_room_target_temperature.call_count == 2
    assert clients[0].sent_at[0] == clients[0].sent_at[1]
    assert _state(hass) == HVACMode.OFF
    state = hass.states.get("climate.room_2")
    assert state
    assert state.state == HVACMode.OFF


async def test_command_sent_when_the_caller_is_cancelled(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_cloud_config_entry: MockConfigEntry,
    clients: list[MagicMock],
) -> None:
    """Test a command is still sent if the caller stops waiting."""
    await setup_integration(hass, mock_cloud_config_entry)

    caller = asyncio.create_task(_set_hvac_mode(hass, HVACMode.OFF))
    for _ in range(10):
        await asyncio.sleep(0)
    caller.cancel()
    with pytest.raises(asyncio.CancelledError):
        await caller

    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    clients[0].set_room_target_temperature.assert_called_once_with("1", 5, False)
    assert _state(hass) == HVACMode.OFF


async def test_poll_waits_for_a_command(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_cloud_config_entry: MockConfigEntry,
    clients: list[MagicMock],
) -> None:
    """Test a poll during a command waits, then fetches once it is allowed."""
    await setup_integration(hass, mock_cloud_config_entry)
    client = clients[0]
    release = asyncio.Event()

    async def _slow(room_id: str, temperature: float, heating_enabled: bool) -> None:
        await release.wait()
        client.rooms[0].update(
            targetTemperature=temperature, heatingEnabled=heating_enabled
        )

    client.set_room_target_temperature.side_effect = _slow
    command = asyncio.create_task(_set_hvac_mode(hass, HVACMode.OFF))
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    for _ in range(10):
        await asyncio.sleep(0)
    client.set_room_target_temperature.assert_called_once()
    fetches = client.fetch_rooms_info.call_count

    # The poll is due while the command is still being sent.
    freezer.tick(timedelta(seconds=29))
    async_fire_time_changed(hass)
    for _ in range(10):
        await asyncio.sleep(0)
    assert client.fetch_rooms_info.call_count == fetches

    release.set()
    await command
    assert _state(hass) == HVACMode.OFF
    client.rooms = _rooms(temperature=16)
    await _tick(hass, freezer, 31)
    assert client.fetch_rooms_info.call_count == fetches + 1
    assert _attr(hass, ClimateEntityStateAttribute.CURRENT_TEMPERATURE) == 16


async def test_command_every_minute(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_cloud_config_entry: MockConfigEntry,
    clients: list[MagicMock],
) -> None:
    """Test regular commands do not stop polls from getting new data."""
    await setup_integration(hass, mock_cloud_config_entry)
    client = clients[0]
    for minute in range(20):
        client.rooms = _rooms(temperature=10 + minute)
        await _run(hass, freezer, _set_hvac_mode(hass, HVACMode.HEAT))
        await _poll(hass, freezer)
        assert _state(hass) == HVACMode.HEAT
        assert _attr(hass, ClimateEntityStateAttribute.CURRENT_TEMPERATURE) == (
            10 + minute
        )
    assert len(clients) == 1


async def test_command_client_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_cloud_config_entry: MockConfigEntry,
    clients: list[MagicMock],
) -> None:
    """Test an error from the client fails the command."""
    await setup_integration(hass, mock_cloud_config_entry)
    clients[0].set_room_target_temperature.side_effect = ValueError

    with pytest.raises(HomeAssistantError) as err:
        await _run(hass, freezer, _set_hvac_mode(hass, HVACMode.OFF))
    assert err.value.translation_key == "command_failed"
    assert _state(hass) == HVACMode.HEAT
    # The client may be left broken, so it is replaced.
    assert len(clients) == 2


async def test_command_waiting_when_unloaded(
    hass: HomeAssistant,
    mock_cloud_config_entry: MockConfigEntry,
    clients: list[MagicMock],
) -> None:
    """Test a command still waiting for the client fails when unloading."""
    await setup_integration(hass, mock_cloud_config_entry)

    caller = asyncio.create_task(_set_hvac_mode(hass, HVACMode.OFF))
    for _ in range(10):
        await asyncio.sleep(0)
    await hass.config_entries.async_unload(mock_cloud_config_entry.entry_id)

    with pytest.raises(HomeAssistantError) as err:
        await caller
    assert err.value.translation_key == "command_timeout"
    clients[0].set_room_target_temperature.assert_not_called()


@pytest.mark.parametrize(
    "start_rooms",
    [
        [
            {**CLOUD_DEVICE_DATA[0]},
            {**CLOUD_DEVICE_DATA[0], "id": "2", "name": "Room 2"},
        ]
    ],
)
async def test_failed_batch_does_not_fail_queued_commands(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_cloud_config_entry: MockConfigEntry,
    clients: list[MagicMock],
) -> None:
    """Test a command queued behind a failing one is sent with the new client."""
    await setup_integration(hass, mock_cloud_config_entry)
    release = asyncio.Event()

    async def _fail(*args: Any) -> None:
        await release.wait()
        raise ConnectionError

    clients[0].set_room_target_temperature.side_effect = _fail
    first = asyncio.create_task(_set_hvac_mode(hass, HVACMode.OFF))
    # Not _tick: async_block_till_done would wait for the pending command.
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    for _ in range(10):
        await asyncio.sleep(0)
    clients[0].set_room_target_temperature.assert_called_once()

    second = asyncio.create_task(
        hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_HVAC_MODE,
            {
                TargetKey.ENTITY_ID: "climate.room_2",
                ClimateServiceArgument.HVAC_MODE: HVACMode.OFF,
            },
            blocking=True,
        )
    )
    for _ in range(10):
        await asyncio.sleep(0)
    release.set()
    with pytest.raises(HomeAssistantError):
        await first

    async def _second() -> None:
        await second

    await _run(hass, freezer, _second())
    assert len(clients) == 2
    clients[1].set_room_target_temperature.assert_called_once_with("2", 5, False)


async def test_poll_sends_queued_commands_first(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_cloud_config_entry: MockConfigEntry,
    clients: list[MagicMock],
) -> None:
    """Test a command queued behind a waiting poll is sent before the fetch."""
    await setup_integration(hass, mock_cloud_config_entry)
    client = clients[0]
    order: list[str] = []
    client.fetch_rooms_info.side_effect = lambda: order.append("fetch")
    sent = client.set_room_target_temperature.side_effect

    async def _record(*args: Any) -> None:
        order.append("command")
        await sent(*args)

    client.set_room_target_temperature.side_effect = _record

    # A command, then a poll that has to wait for the client, then a command.
    await _run(hass, freezer, _set_hvac_mode(hass, HVACMode.OFF))
    order.clear()
    freezer.tick(timedelta(seconds=SCAN_INTERVAL.total_seconds() - 31))
    async_fire_time_changed(hass)
    for _ in range(10):
        await asyncio.sleep(0)
    await _run(hass, freezer, _set_hvac_mode(hass, HVACMode.HEAT))
    await _tick(hass, freezer, 31)
    assert order[:2] == ["command", "fetch"]


async def test_command_with_a_new_client(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_cloud_config_entry: MockConfigEntry,
    clients: list[MagicMock],
) -> None:
    """Test a command from a client without rooms is left to the next poll."""
    await setup_integration(hass, mock_cloud_config_entry)
    clients[0].rooms = []

    await _run(hass, freezer, _set_hvac_mode(hass, HVACMode.OFF))
    clients[0].set_room_target_temperature.assert_called_once_with("1", 5, False)
    assert _state(hass) == HVACMode.HEAT


async def test_poll_connection_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_cloud_config_entry: MockConfigEntry,
    clients: list[MagicMock],
) -> None:
    """Test a connection error during a poll makes the entities unavailable."""
    await setup_integration(hass, mock_cloud_config_entry)
    clients[0].fetch_rooms_info.side_effect = OSError("boom")

    await _poll(hass, freezer)
    assert _state(hass) == STATE_UNAVAILABLE
