"""Tests for Marantz 2007-protocol media players."""

import asyncio
from collections.abc import Callable
import math
from pathlib import Path
from unittest.mock import MagicMock

from marantz_rs232 import V2007ReceiverState, V2007Source
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.marantz_rs232.media_player import INPUT_SOURCE_TO_HA
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MP_DOMAIN,
    SERVICE_SELECT_SOURCE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.json import load_json

MAIN = "media_player.marantz_receiver"
MULTI = "media_player.marantz_receiver_multi_room"


COMMANDS = [
    ("main", MAIN, SERVICE_TURN_ON, {}, "power_on", ()),
    ("main", MAIN, SERVICE_TURN_OFF, {}, "power_off", ()),
    ("main", MAIN, SERVICE_VOLUME_UP, {}, "volume_up", ()),
    ("main", MAIN, SERVICE_VOLUME_DOWN, {}, "volume_down", ()),
    (
        "main",
        MAIN,
        SERVICE_VOLUME_SET,
        {ATTR_MEDIA_VOLUME_LEVEL: 0.5},
        "set_volume",
        (-31.0,),
    ),
    ("main", MAIN, SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: True}, "mute_on", ()),
    (
        "main",
        MAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_MEDIA_VOLUME_MUTED: False},
        "mute_off",
        (),
    ),
    (
        "main",
        MAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_INPUT_SOURCE: "dvd"},
        "select_source",
        (V2007Source.DVD,),
    ),
    ("multi_room_a", MULTI, SERVICE_TURN_ON, {}, "power_on", ()),
    ("multi_room_a", MULTI, SERVICE_TURN_OFF, {}, "power_off", ()),
    ("multi_room_a", MULTI, SERVICE_VOLUME_UP, {}, "line_volume_up", ()),
    ("multi_room_a", MULTI, SERVICE_VOLUME_DOWN, {}, "line_volume_down", ()),
    (
        "multi_room_a",
        MULTI,
        SERVICE_VOLUME_SET,
        {ATTR_MEDIA_VOLUME_LEVEL: 0.5},
        "set_line_volume",
        (-31.0,),
    ),
    (
        "multi_room_a",
        MULTI,
        SERVICE_VOLUME_MUTE,
        {ATTR_MEDIA_VOLUME_MUTED: True},
        "mute_on",
        (),
    ),
    (
        "multi_room_a",
        MULTI,
        SERVICE_VOLUME_MUTE,
        {ATTR_MEDIA_VOLUME_MUTED: False},
        "mute_off",
        (),
    ),
    (
        "multi_room_a",
        MULTI,
        SERVICE_SELECT_SOURCE,
        {ATTR_INPUT_SOURCE: "dvd"},
        "select_source",
        (V2007Source.DVD,),
    ),
]


@pytest.mark.usefixtures("init_integration")
async def test_entities_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Discover both players from initial queries."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_missing_multi_room(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """An unanswered multi-room query must not create a ghost player."""
    mock_receiver.multi_room_a.power = None
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(MAIN) is not None
    assert hass.states.get(MULTI) is None


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("power", "expected"), [(True, STATE_ON), (False, STATE_OFF), (None, STATE_UNKNOWN)]
)
async def test_push_state(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
    receiver_update: Callable[[V2007ReceiverState | None], None],
    power: bool | None,
    expected: str,
) -> None:
    """Follow pushed state for both players."""
    mock_receiver.main.power = power
    mock_receiver.multi_room_a.power = power
    receiver_update(V2007ReceiverState())
    assert hass.states.get(MAIN).state == expected
    assert hass.states.get(MULTI).state == expected


@pytest.mark.usefixtures("init_integration")
async def test_disconnect_reloads(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
    mock_config_entry: MockConfigEntry,
    receiver_update: Callable[[V2007ReceiverState | None], None],
) -> None:
    """Mark both entities unavailable, then reconnect through Home Assistant."""
    reconnect_started = asyncio.Event()
    reconnect_allowed = asyncio.Event()
    connect = mock_receiver.connect.side_effect

    async def reconnect() -> None:
        reconnect_started.set()
        await reconnect_allowed.wait()
        await connect()

    mock_receiver.connect.side_effect = reconnect
    receiver_update(None)
    await reconnect_started.wait()
    assert hass.states.get(MAIN).state == STATE_UNAVAILABLE
    assert hass.states.get(MULTI).state == STATE_UNAVAILABLE
    reconnect_allowed.set()
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_receiver.connect.await_count == 2
    assert mock_receiver.query_state.await_count == 2
    assert mock_receiver.query_multi_room_a.await_count == 2
    mock_receiver.disconnect.assert_awaited_once()
    assert hass.states.get(MAIN).state == STATE_ON
    assert hass.states.get(MULTI).state == STATE_ON


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("volume", "expected"), [(-40.0, 40 / 98), (None, None), (-math.inf, None)]
)
async def test_volume_state(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
    receiver_update: Callable[[V2007ReceiverState | None], None],
    volume: float | None,
    expected: float | None,
) -> None:
    """Never expose the protocol's mute sentinel as infinite volume."""
    mock_receiver.main.volume = volume
    mock_receiver.multi_room_a.line_volume = volume
    receiver_update(V2007ReceiverState())
    assert hass.states.get(MAIN).attributes.get(ATTR_MEDIA_VOLUME_LEVEL) == expected
    assert hass.states.get(MULTI).attributes.get(ATTR_MEDIA_VOLUME_LEVEL) == expected


@pytest.mark.usefixtures("init_integration")
async def test_unknown_source(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
    receiver_update: Callable[[V2007ReceiverState | None], None],
) -> None:
    """Unrecognized sources have no selected input."""
    mock_receiver.main.input_source = None
    receiver_update(V2007ReceiverState())
    assert ATTR_INPUT_SOURCE not in hass.states.get(MAIN).attributes


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("zone", "entity_id", "service", "data", "method", "args"), COMMANDS
)
async def test_commands(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
    zone: str,
    entity_id: str,
    service: str,
    data: dict[str, str | bool | float],
    method: str,
    args: tuple[float | V2007Source, ...],
) -> None:
    """Call the player's public API with the converted service parameters."""
    await hass.services.async_call(
        MP_DOMAIN, service, {ATTR_ENTITY_ID: entity_id, **data}, blocking=True
    )
    getattr(getattr(mock_receiver, zone), method).assert_awaited_once_with(*args)


@pytest.mark.usefixtures("init_integration")
async def test_invalid_source(hass: HomeAssistant) -> None:
    """Reject unsupported input names."""
    with pytest.raises(
        ServiceValidationError, match="Input source nonexistent is not supported"
    ) as err:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: MAIN, ATTR_INPUT_SOURCE: "nonexistent"},
            blocking=True,
        )

    assert err.value.translation_key == "invalid_source"


def test_source_translations() -> None:
    """Translate every 2007-protocol input."""
    strings = load_json(Path("homeassistant/components/marantz_rs232/strings.json"))
    declared = strings["entity"]["media_player"]["receiver"]["state_attributes"][
        "source"
    ]["state"]
    assert set(INPUT_SOURCE_TO_HA.values()) == set(declared)
    assert set(INPUT_SOURCE_TO_HA) == set(V2007Source)


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("error", [ConnectionError, OSError, TimeoutError])
@pytest.mark.parametrize(
    ("zone", "entity_id", "service", "data", "method", "args"), COMMANDS
)
async def test_command_failure(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
    zone: str,
    entity_id: str,
    error: type[Exception],
    service: str,
    data: dict[str, str | bool | float],
    method: str,
    args: tuple[float | V2007Source, ...],
) -> None:
    """Report serial failures as translated action errors for either output."""
    command = getattr(getattr(mock_receiver, zone), method)
    command.side_effect = error("Connection lost")
    with pytest.raises(
        HomeAssistantError, match="Unable to communicate with the receiver"
    ) as err:
        await hass.services.async_call(
            MP_DOMAIN, service, {ATTR_ENTITY_ID: entity_id, **data}, blocking=True
        )
    command.assert_awaited_once_with(*args)
    assert err.value.translation_key == "communication_error"
    assert isinstance(err.value.__cause__, error)


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("zone", "entity_id"), [("main", MAIN), ("multi_room_a", MULTI)]
)
@pytest.mark.parametrize(
    ("source", "code"),
    [("bd", "M"), ("usb", "7"), ("cd", "B"), ("am2", "L")],
)
async def test_other_model_sources(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
    receiver_update: Callable[[V2007ReceiverState | None], None],
    zone: str,
    entity_id: str,
    source: str,
    code: str,
) -> None:
    """Offer and select 2007-protocol inputs absent from the tested SR7002."""
    assert source in hass.states.get(entity_id).attributes["source_list"]
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: entity_id, ATTR_INPUT_SOURCE: source},
        blocking=True,
    )
    getattr(mock_receiver, zone).select_source.assert_awaited_once_with(
        V2007Source(code)
    )
    mock_receiver.main.input_source = V2007Source(code)
    mock_receiver.multi_room_a.input_source = V2007Source(code)
    receiver_update(V2007ReceiverState())
    assert hass.states.get(entity_id).attributes[ATTR_INPUT_SOURCE] == source
