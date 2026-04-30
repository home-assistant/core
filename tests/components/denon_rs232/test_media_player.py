"""Tests for the Denon RS232 media player platform."""

from pathlib import Path
from typing import Literal
from unittest.mock import call

from denon_rs232 import InputSource
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.denon_rs232.media_player import INPUT_SOURCE_DENON_TO_HA
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
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
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.json import load_json

from .conftest import MockReceiver, MockState, _default_state

from tests.common import MockConfigEntry, snapshot_platform

ZoneName = Literal["main", "zone_2", "zone_3"]

MAIN_ENTITY_ID = "media_player.avr_3805"
ZONE_2_ENTITY_ID = "media_player.avr_3805_zone_2"
ZONE_3_ENTITY_ID = "media_player.avr_3805_zone_3"

STRINGS_PATH = Path("homeassistant/components/denon_rs232/strings.json")


@pytest.fixture(autouse=True)
async def auto_init_components(init_components) -> None:
    """Set up the component."""


async def test_entities_created(
    hass: HomeAssistant,
    mock_receiver: MockReceiver,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test media player entities are created through config entry setup."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
    mock_receiver.query_state.assert_awaited_once()


@pytest.mark.parametrize("initial_receiver_state", ["main_only"], indirect=True)
async def test_only_active_zones_are_created(
    hass: HomeAssistant, initial_receiver_state: MockState
) -> None:
    """Test setup only creates entities for zones with queried power state."""
    assert hass.states.get(MAIN_ENTITY_ID) is not None
    assert hass.states.get(ZONE_2_ENTITY_ID) is None
    assert hass.states.get(ZONE_3_ENTITY_ID) is None


@pytest.mark.parametrize(
    ("zone", "entity_id", "initial_entity_state"),
    [
        ("main", MAIN_ENTITY_ID, STATE_ON),
        ("zone_2", ZONE_2_ENTITY_ID, STATE_ON),
        ("zone_3", ZONE_3_ENTITY_ID, STATE_OFF),
    ],
)
async def test_zone_state_updates(
    hass: HomeAssistant,
    mock_receiver: MockReceiver,
    zone: ZoneName,
    entity_id: str,
    initial_entity_state: str,
) -> None:
    """Test each zone updates from receiver pushes and disconnects."""
    assert hass.states.get(entity_id).state == initial_entity_state

    state = _default_state()
    state.get_zone(zone).power = initial_entity_state != STATE_ON
    mock_receiver.mock_state(state)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state != initial_entity_state

    mock_receiver.mock_state(None)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("zone", "entity_id", "power_on_command", "power_off_command"),
    [
        ("main", MAIN_ENTITY_ID, ("ZM", "ON"), ("ZM", "OFF")),
        ("zone_2", ZONE_2_ENTITY_ID, ("Z2", "ON"), ("Z2", "OFF")),
        ("zone_3", ZONE_3_ENTITY_ID, ("Z1", "ON"), ("Z1", "OFF")),
    ],
)
async def test_power_controls(
    hass: HomeAssistant,
    mock_receiver: MockReceiver,
    zone: ZoneName,
    entity_id: str,
    power_on_command: tuple[str, str],
    power_off_command: tuple[str, str],
) -> None:
    """Test power services send the right commands for each zone."""

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert mock_receiver._send_command.await_args == call(*power_on_command)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert mock_receiver._send_command.await_args == call(*power_off_command)


@pytest.mark.parametrize(
    (
        "zone",
        "entity_id",
        "initial_volume_level",
        "set_command",
        "volume_up_command",
        "volume_down_command",
    ),
    [
        (
            "main",
            MAIN_ENTITY_ID,
            50.0 / 90.0,
            ("MV", "45"),
            ("MV", "UP"),
            ("MV", "DOWN"),
        ),
        (
            "zone_2",
            ZONE_2_ENTITY_ID,
            60.0 / 90.0,
            ("Z2", "45"),
            ("Z2", "UP"),
            ("Z2", "DOWN"),
        ),
    ],
)
async def test_volume_controls(
    hass: HomeAssistant,
    mock_receiver: MockReceiver,
    zone: ZoneName,
    entity_id: str,
    initial_volume_level: float,
    set_command: tuple[str, str],
    volume_up_command: tuple[str, str],
    volume_down_command: tuple[str, str],
) -> None:
    """Test volume state and controls for each zone."""
    state = hass.states.get(entity_id)

    assert abs(state.attributes[ATTR_MEDIA_VOLUME_LEVEL] - initial_volume_level) < 0.001

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: entity_id, ATTR_MEDIA_VOLUME_LEVEL: 0.5},
        blocking=True,
    )
    assert mock_receiver._send_command.await_args == call(*set_command)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_UP,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert mock_receiver._send_command.await_args == call(*volume_up_command)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_DOWN,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert mock_receiver._send_command.await_args == call(*volume_down_command)


async def test_main_mute_controls(
    hass: HomeAssistant, mock_receiver: MockReceiver
) -> None:
    """Test mute state and controls for the main zone."""
    state = hass.states.get(MAIN_ENTITY_ID)

    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is False

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: MAIN_ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: True},
        blocking=True,
    )
    assert mock_receiver._send_command.await_args == call("MU", "ON")

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: MAIN_ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: False},
        blocking=True,
    )
    assert mock_receiver._send_command.await_args == call("MU", "OFF")


@pytest.mark.parametrize(
    (
        "zone",
        "entity_id",
        "initial_source",
        "updated_source",
        "expected_source",
        "select_source_command",
    ),
    [
        ("main", MAIN_ENTITY_ID, "cd", InputSource.NET, "net", ("SI", "NET")),
        (
            "zone_2",
            ZONE_2_ENTITY_ID,
            "tuner",
            InputSource.BT,
            "bt",
            ("Z2", "BT"),
        ),
        ("zone_3", ZONE_3_ENTITY_ID, None, InputSource.DVD, "dvd", ("Z1", "DVD")),
    ],
)
async def test_source_state_and_controls(
    hass: HomeAssistant,
    mock_receiver: MockReceiver,
    zone: ZoneName,
    entity_id: str,
    initial_source: str | None,
    updated_source: InputSource,
    expected_source: str,
    select_source_command: tuple[str, str],
) -> None:
    """Test source state and selection for each zone."""
    entity_state = hass.states.get(entity_id)

    assert entity_state.attributes.get(ATTR_INPUT_SOURCE) == initial_source

    source_list = entity_state.attributes[ATTR_INPUT_SOURCE_LIST]
    assert "cd" in source_list
    assert "dvd" in source_list
    assert "tuner" in source_list
    assert source_list == sorted(source_list)

    state = _default_state()
    zone_state = state.get_zone(zone)
    zone_state.power = True
    zone_state.input_source = updated_source
    mock_receiver.mock_state(state)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).attributes[ATTR_INPUT_SOURCE] == expected_source

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: entity_id, ATTR_INPUT_SOURCE: expected_source},
        blocking=True,
    )
    assert mock_receiver._send_command.await_args == call(*select_source_command)


async def test_main_invalid_source_raises(
    hass: HomeAssistant,
) -> None:
    """Test invalid main-zone sources raise an error."""
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {
                ATTR_ENTITY_ID: MAIN_ENTITY_ID,
                ATTR_INPUT_SOURCE: "NONEXISTENT",
            },
            blocking=True,
        )


def test_input_source_translation_keys_cover_all_enum_members() -> None:
    """Test all input sources have a declared translation key."""
    assert set(INPUT_SOURCE_DENON_TO_HA) == set(InputSource)

    strings = load_json(STRINGS_PATH)
    assert set(INPUT_SOURCE_DENON_TO_HA.values()) == set(
        strings["entity"]["media_player"]["receiver"]["state_attributes"]["source"][
            "state"
        ]
    )
