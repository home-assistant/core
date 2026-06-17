"""Tests for the Marantz RS-232 media player platform."""

from pathlib import Path

from marantz_rs232 import (
    MarantzV2003Receiver,
    MarantzV2007Receiver,
    MarantzV2015Receiver,
    V2015InputSource,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.marantz_rs232.const import DOMAIN
from homeassistant.components.marantz_rs232.media_player import (
    INPUT_SOURCE_V2003_TO_HA,
    INPUT_SOURCE_V2007_TO_HA,
    INPUT_SOURCE_V2015_TO_HA,
)
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
    CONF_DEVICE,
    CONF_MODEL,
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

from . import MOCK_DEVICE
from .conftest import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

MAIN_ENTITY_ID = "media_player.modern"
ZONE_2_ENTITY_ID = "media_player.modern_zone_2"
ZONE_3_ENTITY_ID = "media_player.modern_zone_3"

STRINGS_PATH = Path("homeassistant/components/marantz_rs232/strings.json")


@pytest.fixture
async def init_v2015(
    hass: HomeAssistant,
    mock_v2015_receiver: MarantzV2015Receiver,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Set up the modern receiver."""
    await setup_integration(
        hass, mock_config_entry, mock_v2015_receiver, "MarantzV2015Receiver"
    )


async def test_entities_created(
    hass: HomeAssistant,
    mock_v2015_receiver: MarantzV2015Receiver,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    init_v2015: None,
) -> None:
    """Test media player entities are created through config entry setup."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
    mock_v2015_receiver.query_state.assert_awaited_once()


async def test_inactive_zone_not_created(
    hass: HomeAssistant,
    mock_v2015_receiver: MarantzV2015Receiver,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test zones without a queried power state are not created."""
    mock_v2015_receiver._state.zone_2.power = None
    mock_v2015_receiver._state.zone_3.power = None

    await setup_integration(
        hass, mock_config_entry, mock_v2015_receiver, "MarantzV2015Receiver"
    )

    assert hass.states.get(MAIN_ENTITY_ID) is not None
    assert hass.states.get(ZONE_2_ENTITY_ID) is None
    assert hass.states.get(ZONE_3_ENTITY_ID) is None


async def test_state_update_and_unavailable(
    hass: HomeAssistant,
    mock_v2015_receiver: MarantzV2015Receiver,
    init_v2015: None,
) -> None:
    """Test the entity follows pushed state and goes unavailable on disconnect."""
    assert hass.states.get(MAIN_ENTITY_ID).state == STATE_ON

    mock_v2015_receiver._state.main_zone.power = False
    mock_v2015_receiver._notify_subscribers()
    await hass.async_block_till_done()
    assert hass.states.get(MAIN_ENTITY_ID).state == STATE_OFF

    mock_v2015_receiver._connected = False
    mock_v2015_receiver._notify_subscribers()
    await hass.async_block_till_done()
    assert hass.states.get(MAIN_ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("entity_id", "service", "data", "expected"),
    [
        (MAIN_ENTITY_ID, SERVICE_TURN_ON, {}, ("ZM", "ON")),
        (MAIN_ENTITY_ID, SERVICE_TURN_OFF, {}, ("ZM", "OFF")),
        (MAIN_ENTITY_ID, SERVICE_VOLUME_UP, {}, ("MV", "UP")),
        (MAIN_ENTITY_ID, SERVICE_VOLUME_DOWN, {}, ("MV", "DOWN")),
        (
            MAIN_ENTITY_ID,
            SERVICE_VOLUME_MUTE,
            {ATTR_MEDIA_VOLUME_MUTED: True},
            ("MU", "ON"),
        ),
        (
            MAIN_ENTITY_ID,
            SERVICE_VOLUME_MUTE,
            {ATTR_MEDIA_VOLUME_MUTED: False},
            ("MU", "OFF"),
        ),
        (
            MAIN_ENTITY_ID,
            SERVICE_SELECT_SOURCE,
            {ATTR_INPUT_SOURCE: "net"},
            ("SI", V2015InputSource.NET.value),
        ),
        (ZONE_2_ENTITY_ID, SERVICE_TURN_ON, {}, ("Z2", "ON")),
        (
            ZONE_2_ENTITY_ID,
            SERVICE_SELECT_SOURCE,
            {ATTR_INPUT_SOURCE: "cd"},
            ("Z2", V2015InputSource.CD.value),
        ),
    ],
)
async def test_v2015_commands(
    hass: HomeAssistant,
    mock_v2015_receiver: MarantzV2015Receiver,
    init_v2015: None,
    entity_id: str,
    service: str,
    data: dict[str, str | bool],
    expected: tuple[str, str],
) -> None:
    """Test media player services send the expected serial commands."""
    await hass.services.async_call(
        MP_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id, **data},
        blocking=True,
    )
    mock_v2015_receiver._send_command.assert_awaited_with(*expected)


async def test_v2015_volume_set(
    hass: HomeAssistant,
    mock_v2015_receiver: MarantzV2015Receiver,
    init_v2015: None,
) -> None:
    """Test setting the volume level sends a volume command."""
    state = hass.states.get(MAIN_ENTITY_ID)
    # volume -40 in range [-80, 18] -> (-40 - -80) / 98
    assert abs(state.attributes[ATTR_MEDIA_VOLUME_LEVEL] - (40 / 98)) < 0.001

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: MAIN_ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.5},
        blocking=True,
    )
    assert mock_v2015_receiver._send_command.await_args.args[0] == "MV"


async def test_invalid_source_raises(
    hass: HomeAssistant,
    init_v2015: None,
) -> None:
    """Test selecting an unknown source raises an error."""
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: MAIN_ENTITY_ID, ATTR_INPUT_SOURCE: "nonexistent"},
            blocking=True,
        )


async def test_v2007_entities(
    hass: HomeAssistant,
    mock_v2007_receiver: MarantzV2007Receiver,
) -> None:
    """Test a 2007-era receiver creates main and multi-room entities."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: MOCK_DEVICE, CONF_MODEL: "sr7002"},
        title="SR7002",
    )
    await setup_integration(hass, entry, mock_v2007_receiver, "MarantzV2007Receiver")

    main = hass.states.get("media_player.sr7002")
    assert main.state == STATE_ON
    assert main.attributes[ATTR_INPUT_SOURCE] == "dvd"
    assert hass.states.get("media_player.sr7002_multi_room") is not None

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "media_player.sr7002"},
        blocking=True,
    )
    assert mock_v2007_receiver._send_command.await_args.args[0] == "PWR"

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: "media_player.sr7002", ATTR_INPUT_SOURCE: "tv"},
        blocking=True,
    )
    assert mock_v2007_receiver._send_command.await_args.args[0] == "SRC"

    for service, data in (
        (SERVICE_TURN_OFF, {}),
        (SERVICE_VOLUME_UP, {}),
        (SERVICE_VOLUME_DOWN, {}),
        (SERVICE_VOLUME_SET, {ATTR_MEDIA_VOLUME_LEVEL: 0.5}),
        (SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: True}),
        (SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: False}),
    ):
        await hass.services.async_call(
            MP_DOMAIN,
            service,
            {ATTR_ENTITY_ID: "media_player.sr7002", **data},
            blocking=True,
        )

    # Exercise the multi-room volume/mute/source paths.
    for service, data in (
        (SERVICE_TURN_ON, {}),
        (SERVICE_VOLUME_UP, {}),
        (SERVICE_VOLUME_DOWN, {}),
        (SERVICE_VOLUME_SET, {ATTR_MEDIA_VOLUME_LEVEL: 0.4}),
        (SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: True}),
        (SERVICE_SELECT_SOURCE, {ATTR_INPUT_SOURCE: "dvd"}),
    ):
        await hass.services.async_call(
            MP_DOMAIN,
            service,
            {ATTR_ENTITY_ID: "media_player.sr7002_multi_room", **data},
            blocking=True,
        )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: "media_player.sr7002", ATTR_INPUT_SOURCE: "nope"},
            blocking=True,
        )

    mock_v2007_receiver._state.main.power = False
    mock_v2007_receiver._notify_subscribers()
    await hass.async_block_till_done()
    assert hass.states.get("media_player.sr7002").state == STATE_OFF

    mock_v2007_receiver._connected = False
    mock_v2007_receiver._notify_subscribers()
    await hass.async_block_till_done()
    assert hass.states.get("media_player.sr7002").state == STATE_UNAVAILABLE


async def test_v2003_entities(
    hass: HomeAssistant,
    mock_v2003_receiver: MarantzV2003Receiver,
) -> None:
    """Test a 2003-era receiver creates main and multi-room entities."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: MOCK_DEVICE, CONF_MODEL: "sr9300"},
        title="SR9300",
    )
    await setup_integration(hass, entry, mock_v2003_receiver, "MarantzV2003Receiver")

    main = hass.states.get("media_player.sr9300")
    assert main.state == STATE_ON
    assert main.attributes[ATTR_INPUT_SOURCE] == "cd"

    multi_room = hass.states.get("media_player.sr9300_multi_room")
    assert multi_room is not None
    assert ATTR_INPUT_SOURCE_LIST in multi_room.attributes

    for service, data in (
        (SERVICE_TURN_ON, {}),
        (SERVICE_TURN_OFF, {}),
        (SERVICE_VOLUME_UP, {}),
        (SERVICE_VOLUME_DOWN, {}),
        (SERVICE_VOLUME_SET, {ATTR_MEDIA_VOLUME_LEVEL: 0.5}),
        (SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: True}),
        (SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: False}),
        (SERVICE_SELECT_SOURCE, {ATTR_INPUT_SOURCE: "dvd"}),
    ):
        await hass.services.async_call(
            MP_DOMAIN,
            service,
            {ATTR_ENTITY_ID: "media_player.sr9300", **data},
            blocking=True,
        )
    mock_v2003_receiver._send_command.assert_awaited()

    # Exercise multi-room power/volume/source paths.
    for service, data in (
        (SERVICE_TURN_ON, {}),
        (SERVICE_TURN_OFF, {}),
        (SERVICE_VOLUME_UP, {}),
        (SERVICE_VOLUME_DOWN, {}),
        (SERVICE_SELECT_SOURCE, {ATTR_INPUT_SOURCE: "tuner"}),
    ):
        await hass.services.async_call(
            MP_DOMAIN,
            service,
            {ATTR_ENTITY_ID: "media_player.sr9300_multi_room", **data},
            blocking=True,
        )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: "media_player.sr9300", ATTR_INPUT_SOURCE: "nope"},
            blocking=True,
        )

    mock_v2003_receiver._state.main.power = False
    mock_v2003_receiver._notify(mock_v2003_receiver._state)
    await hass.async_block_till_done()
    assert hass.states.get("media_player.sr9300").state == STATE_OFF

    mock_v2003_receiver._connected = False
    mock_v2003_receiver._notify(None)
    await hass.async_block_till_done()
    assert hass.states.get("media_player.sr9300").state == STATE_UNAVAILABLE


def test_translation_keys_cover_all_sources() -> None:
    """Test every mapped source has a matching translation key and vice versa."""
    mapped = (
        set(INPUT_SOURCE_V2015_TO_HA.values())
        | set(INPUT_SOURCE_V2007_TO_HA.values())
        | set(INPUT_SOURCE_V2003_TO_HA.values())
    )

    strings = load_json(STRINGS_PATH)
    declared = set(
        strings["entity"]["media_player"]["receiver"]["state_attributes"]["source"][
            "state"
        ]
    )
    assert mapped == declared
