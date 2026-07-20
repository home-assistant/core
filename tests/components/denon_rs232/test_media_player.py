"""Tests for the Denon RS-232 media player platform."""

from pathlib import Path
from typing import Literal
from unittest.mock import call

from denon_rs232 import InputSource
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.denon_rs232.media_player import (
    INPUT_SOURCE_DENON_TO_HA,
    TUNER_PRESETS_ROOT,
)
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_CHANNEL,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MP_DOMAIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOURCE,
    MediaType,
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
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.json import load_json

from .conftest import MockReceiver, MockState, _default_state

from tests.common import MockConfigEntry, snapshot_platform
from tests.typing import WebSocketGenerator

type ZoneName = Literal["main", "zone_2", "zone_3"]

MAIN_ENTITY_ID = "media_player.avr_3805"
ZONE_2_ENTITY_ID = "media_player.avr_3805_zone_2"
ZONE_3_ENTITY_ID = "media_player.avr_3805_zone_3"

STRINGS_PATH = Path("homeassistant/components/denon_rs232/strings.json")

# The 56 tuner presets the integration exposes, A1 through G8.
TUNER_PRESETS = [f"{bank}{number}" for bank in "ABCDEFG" for number in range(1, 9)]


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


@pytest.mark.parametrize(
    ("media_id", "expected_command"),
    [
        pytest.param("A1", ("TP", "A1"), id="first_preset"),
        pytest.param("G8", ("TP", "G8"), id="last_preset"),
        pytest.param("C5", ("TP", "C5"), id="preset"),
        pytest.param("8750", ("TF", "008750"), id="lowest_frequency"),
        pytest.param("10800", ("TF", "010800"), id="highest_frequency"),
        pytest.param("9930", ("TF", "009930"), id="frequency"),
        pytest.param("009930", ("TF", "009930"), id="padded_frequency"),
        pytest.param("00009930", ("TF", "009930"), id="overpadded_frequency"),
        pytest.param("0000008750", ("TF", "008750"), id="overpadded_lowest_frequency"),
        pytest.param(
            "0" * 5000 + "8750", ("TF", "008750"), id="leading_zeros_beyond_int_limit"
        ),
    ],
)
async def test_main_tuner_play_media(
    hass: HomeAssistant,
    mock_receiver: MockReceiver,
    media_id: str,
    expected_command: tuple[str, str],
) -> None:
    """Test playing media selects a tuner preset or frequency.

    The default main input source is CD, so this also covers tuning while the
    main zone plays another source.
    """
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: MAIN_ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: MediaType.CHANNEL,
            ATTR_MEDIA_CONTENT_ID: media_id,
        },
        blocking=True,
    )
    assert mock_receiver._send_command.await_args == call(*expected_command)


@pytest.mark.parametrize(
    ("media_type", "media_id", "translation_key"),
    [
        pytest.param(
            MediaType.MUSIC, "A1", "unsupported_media_type", id="media_type_not_channel"
        ),
        pytest.param(
            MediaType.CHANNEL, "A", "invalid_tuner_channel", id="media_id_too_short"
        ),
        pytest.param(
            MediaType.CHANNEL, "H1", "invalid_tuner_channel", id="preset_bank_above"
        ),
        pytest.param(
            MediaType.CHANNEL, "A0", "invalid_tuner_channel", id="preset_number_zero"
        ),
        pytest.param(
            MediaType.CHANNEL, "A9", "invalid_tuner_channel", id="preset_number_above"
        ),
        pytest.param(
            MediaType.CHANNEL, "a1", "invalid_tuner_channel", id="preset_lowercase"
        ),
        pytest.param(
            MediaType.CHANNEL, "A1B", "invalid_tuner_channel", id="preset_too_long"
        ),
        pytest.param(
            MediaType.CHANNEL,
            "8749",
            "invalid_tuner_channel",
            id="frequency_below_range",
        ),
        pytest.param(
            MediaType.CHANNEL,
            "10801",
            "invalid_tuner_channel",
            id="frequency_above_range",
        ),
        pytest.param(
            MediaType.CHANNEL, "1000", "invalid_tuner_channel", id="am_frequency"
        ),
        pytest.param(
            MediaType.CHANNEL,
            "99.30",
            "invalid_tuner_channel",
            id="frequency_not_an_integer",
        ),
        pytest.param(
            MediaType.CHANNEL, "not a channel", "invalid_tuner_channel", id="unparsable"
        ),
        pytest.param(
            MediaType.CHANNEL,
            "9" * 5000,
            "invalid_tuner_channel",
            id="frequency_exceeds_int_conversion_limit",
        ),
        pytest.param(
            MediaType.CHANNEL,
            "0" * 5000,
            "invalid_tuner_channel",
            id="zeros_exceed_int_conversion_limit",
        ),
    ],
)
async def test_main_tuner_play_media_invalid_input_raises(
    hass: HomeAssistant,
    mock_receiver: MockReceiver,
    media_type: MediaType,
    media_id: str,
    translation_key: str,
) -> None:
    """Test playing invalid media raises and sends no tuner command."""
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: MAIN_ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: media_type,
                ATTR_MEDIA_CONTENT_ID: media_id,
            },
            blocking=True,
        )

    assert err.value.translation_key == translation_key
    assert mock_receiver._send_command.await_count == 0


@pytest.mark.parametrize("entity_id", [ZONE_2_ENTITY_ID, ZONE_3_ENTITY_ID])
async def test_zones_do_not_support_play_media(
    hass: HomeAssistant, entity_id: str
) -> None:
    """Test playing media is rejected for zones, which have no tuner control."""
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.CHANNEL,
                ATTR_MEDIA_CONTENT_ID: "A1",
            },
            blocking=True,
        )


@pytest.mark.parametrize(
    ("tuner_frequency", "expected_channel"),
    [
        pytest.param("009930", "99.30", id="fm_frequency"),
        pytest.param("008750", "87.50", id="lowest_fm_frequency"),
        pytest.param("010800", "108.00", id="highest_fm_frequency"),
        pytest.param("010000", "100.00", id="whole_mhz_frequency"),
        pytest.param(None, None, id="frequency_unknown"),
        pytest.param("050000", None, id="am_threshold"),
        pytest.param("099990", None, id="am_frequency"),
        pytest.param("00AM10", None, id="not_a_number"),
    ],
)
async def test_tuner_frequency_media_channel(
    hass: HomeAssistant,
    mock_receiver: MockReceiver,
    tuner_frequency: str | None,
    expected_channel: str | None,
) -> None:
    """Test the tuner frequency is reported in MHz as the media channel."""
    state = _default_state()
    state.main_zone.input_source = InputSource.TUNER
    state.main_zone.tuner_frequency = tuner_frequency
    mock_receiver.mock_state(state)
    await hass.async_block_till_done()

    entity_state = hass.states.get(MAIN_ENTITY_ID)
    assert entity_state.attributes.get(ATTR_MEDIA_CHANNEL) == expected_channel


async def test_tuner_frequency_not_reported_for_other_sources(
    hass: HomeAssistant, mock_receiver: MockReceiver
) -> None:
    """Test the media channel is cleared when the zone leaves the tuner source."""
    state = _default_state()
    state.main_zone.input_source = InputSource.TUNER
    mock_receiver.mock_state(state)
    await hass.async_block_till_done()

    assert hass.states.get(MAIN_ENTITY_ID).attributes[ATTR_MEDIA_CHANNEL] == "99.30"

    state = _default_state()
    state.main_zone.input_source = InputSource.CD
    mock_receiver.mock_state(state)
    await hass.async_block_till_done()

    entity_state = hass.states.get(MAIN_ENTITY_ID)
    assert ATTR_MEDIA_CHANNEL not in entity_state.attributes


async def test_tuner_frequency_shared_by_zones(
    hass: HomeAssistant, mock_receiver: MockReceiver
) -> None:
    """Test a zone on the tuner source reports the shared main zone frequency."""
    state = _default_state()
    state.main_zone.tuner_frequency = "010110"
    mock_receiver.mock_state(state)
    await hass.async_block_till_done()

    entity_state = hass.states.get(ZONE_2_ENTITY_ID)
    assert entity_state.attributes[ATTR_MEDIA_CHANNEL] == "101.10"


async def test_browse_media_lists_tuner_presets(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test browsing returns every tuner preset as a playable channel."""
    client = await hass_ws_client()
    await client.send_json_auto_id(
        {
            "type": "media_player/browse_media",
            "entity_id": MAIN_ENTITY_ID,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    result = response["result"]
    assert result["media_content_id"] == TUNER_PRESETS_ROOT
    assert not result["can_play"]
    assert result["can_expand"]

    children = result["children"]
    preset_ids = [child["media_content_id"] for child in children]
    assert len(preset_ids) == 56
    assert (preset_ids[0], preset_ids[-1]) == ("A1", "G8")
    assert preset_ids == TUNER_PRESETS
    assert children[0] == {
        "title": "A1",
        "media_class": "channel",
        "media_content_type": "channel",
        "media_content_id": "A1",
        "can_play": True,
        "can_expand": False,
        "can_search": False,
        "thumbnail": None,
        "children_media_class": None,
    }


async def test_browse_media_invalid_content_id(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test browsing an unknown content id fails."""
    client = await hass_ws_client()
    await client.send_json_auto_id(
        {
            "type": "media_player/browse_media",
            "entity_id": MAIN_ENTITY_ID,
            "media_content_id": "unknown",
        }
    )
    response = await client.receive_json()

    assert not response["success"]


@pytest.mark.parametrize("entity_id", [ZONE_2_ENTITY_ID, ZONE_3_ENTITY_ID])
async def test_browse_media_not_supported_for_zones(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, entity_id: str
) -> None:
    """Test only the main zone controls the shared tuner presets."""
    client = await hass_ws_client()
    await client.send_json_auto_id(
        {
            "type": "media_player/browse_media",
            "entity_id": entity_id,
        }
    )
    response = await client.receive_json()

    assert not response["success"]


async def test_browsed_preset_tunes_when_played(
    hass: HomeAssistant, mock_receiver: MockReceiver
) -> None:
    """Test every browsed preset is a valid play_media input."""
    for preset in TUNER_PRESETS:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: MAIN_ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.CHANNEL,
                ATTR_MEDIA_CONTENT_ID: preset,
            },
            blocking=True,
        )
        assert mock_receiver._send_command.await_args == call("TP", preset)


def test_input_source_translation_keys_cover_all_enum_members() -> None:
    """Test all input sources have a declared translation key."""
    assert set(INPUT_SOURCE_DENON_TO_HA) == set(InputSource)

    strings = load_json(STRINGS_PATH)
    assert set(INPUT_SOURCE_DENON_TO_HA.values()) == set(
        strings["entity"]["media_player"]["receiver"]["state_attributes"]["source"][
            "state"
        ]
    )
