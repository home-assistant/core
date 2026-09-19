"""Tests for Marantz 2007-protocol media players."""

import math
from pathlib import Path
from unittest.mock import patch

from marantz_rs232 import MarantzV2007Receiver, V2007Source
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.marantz_rs232.media_player import INPUT_SOURCE_TO_HA
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MP_DOMAIN,
    SERVICE_SELECT_SOURCE,
)
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

from tests.common import MockConfigEntry, snapshot_platform

MAIN = "media_player.marantz_receiver"
MULTI = "media_player.marantz_receiver_multi_room"


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
    mock_receiver: MarantzV2007Receiver,
    mock_config_entry: MockConfigEntry,
) -> None:
    """An unanswered multi-room query must not create a ghost player."""
    mock_receiver.query_multi_room_a.side_effect = None
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
    mock_receiver: MarantzV2007Receiver,
    power: bool | None,
    expected: str,
) -> None:
    """Follow pushed state for both players."""
    mock_receiver._state.main.power = power
    mock_receiver._state.multi_room_a.power = power
    mock_receiver._notify_subscribers()
    assert hass.states.get(MAIN).state == expected
    assert hass.states.get(MULTI).state == expected


@pytest.mark.usefixtures("init_integration")
async def test_disconnect_reloads(
    hass: HomeAssistant,
    mock_receiver: MarantzV2007Receiver,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Mark both entities unavailable and request one reload."""
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        await mock_receiver.disconnect()
        reload.assert_called_once_with(mock_config_entry.entry_id)
    assert hass.states.get(MAIN).state == STATE_UNAVAILABLE
    assert hass.states.get(MULTI).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("volume", "expected"), [(-40.0, 40 / 98), (None, None), (-math.inf, None)]
)
async def test_volume_state(
    hass: HomeAssistant,
    mock_receiver: MarantzV2007Receiver,
    volume: float | None,
    expected: float | None,
) -> None:
    """Never expose the protocol's mute sentinel as infinite volume."""
    mock_receiver._state.main.volume = volume
    mock_receiver._state.multi_room_a.line_volume = volume
    mock_receiver._notify_subscribers()
    assert hass.states.get(MAIN).attributes.get(ATTR_MEDIA_VOLUME_LEVEL) == expected
    assert hass.states.get(MULTI).attributes.get(ATTR_MEDIA_VOLUME_LEVEL) == expected


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("source", [None, "?"])
async def test_unknown_source(
    hass: HomeAssistant,
    mock_receiver: MarantzV2007Receiver,
    source: str | None,
) -> None:
    """Unrecognized sources have no selected input."""
    mock_receiver._state.main.source_audio = source
    mock_receiver._notify_subscribers()
    assert ATTR_INPUT_SOURCE not in hass.states.get(MAIN).attributes


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("entity_id", "service", "data", "expected", "kwargs"),
    [
        (MAIN, SERVICE_TURN_ON, {}, ("PWR", "2"), {}),
        (MAIN, SERVICE_TURN_OFF, {}, ("PWR", "1"), {}),
        (MAIN, SERVICE_VOLUME_UP, {}, ("VOL", "1"), {}),
        (MAIN, SERVICE_VOLUME_DOWN, {}, ("VOL", "2"), {}),
        (
            MAIN,
            SERVICE_VOLUME_SET,
            {ATTR_MEDIA_VOLUME_LEVEL: 0.5},
            ("VOL", "0-310"),
            {},
        ),
        (MAIN, SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: True}, ("AMT", "2"), {}),
        (MAIN, SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: False}, ("AMT", "1"), {}),
        (MAIN, SERVICE_SELECT_SOURCE, {ATTR_INPUT_SOURCE: "dvd"}, ("SRC", "2"), {}),
        (MULTI, SERVICE_TURN_ON, {}, ("MPW", "2"), {"separator": ":"}),
        (MULTI, SERVICE_TURN_OFF, {}, ("MPW", "1"), {"separator": ":"}),
        (MULTI, SERVICE_VOLUME_UP, {}, ("MVL", "1"), {"separator": ":"}),
        (MULTI, SERVICE_VOLUME_DOWN, {}, ("MVL", "2"), {"separator": ":"}),
        (
            MULTI,
            SERVICE_VOLUME_SET,
            {ATTR_MEDIA_VOLUME_LEVEL: 0.5},
            ("MVL", "0-310"),
            {"separator": ":"},
        ),
        (
            MULTI,
            SERVICE_VOLUME_MUTE,
            {ATTR_MEDIA_VOLUME_MUTED: True},
            ("MAM", "2"),
            {"separator": ":"},
        ),
        (
            MULTI,
            SERVICE_VOLUME_MUTE,
            {ATTR_MEDIA_VOLUME_MUTED: False},
            ("MAM", "1"),
            {"separator": ":"},
        ),
        (
            MULTI,
            SERVICE_SELECT_SOURCE,
            {ATTR_INPUT_SOURCE: "dvd"},
            ("MSC", "2"),
            {"separator": ":"},
        ),
    ],
)
async def test_commands(
    hass: HomeAssistant,
    mock_receiver: MarantzV2007Receiver,
    entity_id: str,
    service: str,
    data: dict[str, str | bool | float],
    expected: tuple[str, str],
    kwargs: dict[str, str],
) -> None:
    """Send the correct wire command to each output."""
    await hass.services.async_call(
        MP_DOMAIN, service, {ATTR_ENTITY_ID: entity_id, **data}, blocking=True
    )
    mock_receiver._send_command.assert_awaited_once_with(*expected, **kwargs)


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
@pytest.mark.parametrize("entity_id", [MAIN, MULTI])
@pytest.mark.parametrize("error", [ConnectionError, OSError, TimeoutError])
@pytest.mark.parametrize(
    ("service", "data"),
    [
        (SERVICE_TURN_ON, {}),
        (SERVICE_TURN_OFF, {}),
        (SERVICE_VOLUME_UP, {}),
        (SERVICE_VOLUME_DOWN, {}),
        (SERVICE_VOLUME_SET, {ATTR_MEDIA_VOLUME_LEVEL: 0.5}),
        (SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: True}),
        (SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: False}),
        (SERVICE_SELECT_SOURCE, {ATTR_INPUT_SOURCE: "dvd"}),
    ],
)
async def test_command_failure(
    hass: HomeAssistant,
    mock_receiver: MarantzV2007Receiver,
    entity_id: str,
    error: type[Exception],
    service: str,
    data: dict[str, str | bool | float],
) -> None:
    """Report serial failures as translated action errors for either output."""
    mock_receiver._send_command.side_effect = error("Connection lost")
    with pytest.raises(
        HomeAssistantError, match="Unable to communicate with the receiver"
    ) as err:
        await hass.services.async_call(
            MP_DOMAIN, service, {ATTR_ENTITY_ID: entity_id, **data}, blocking=True
        )
    assert err.value.translation_key == "communication_error"
    assert isinstance(err.value.__cause__, error)


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("entity_id", [MAIN, MULTI])
@pytest.mark.parametrize(
    ("source", "code"),
    [("bd", "M"), ("usb", "7"), ("cd", "B"), ("am2", "L")],
)
async def test_other_model_sources(
    hass: HomeAssistant,
    mock_receiver: MarantzV2007Receiver,
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
    assert mock_receiver._send_command.call_args.args[1] == code
    mock_receiver._state.main.source_audio = code
    mock_receiver._state.multi_room_a.source_audio = code
    mock_receiver._notify_subscribers()
    assert hass.states.get(entity_id).attributes[ATTR_INPUT_SOURCE] == source
