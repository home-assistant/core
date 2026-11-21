"""Test Onkyo media player platform."""

import asyncio
from collections.abc import AsyncGenerator
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aioonkyo import (
    Code,
    Instruction,
    Kind,
    NetArtPacket,
    NetArtType,
    NetPlaybackState,
    NetRepeatMode,
    NetShuffleMode,
    Status,
    Zone,
    command,
    query,
    status,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_fire_time_changed_exact,
    snapshot_platform,
)
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_POSITION_UPDATED_AT,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_TRACK,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_SOUND_MODE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
    MediaPlayerEntityFeature,
    MediaType,
)
from homeassistant.components.media_player.const import DATA_COMPONENT
from homeassistant.components.onkyo.media_player import (
    QUERY_AV_INFO_DELAY,
    QUERY_NET_DELAY,
    QUERY_STATE_DELAY,
)
from homeassistant.components.onkyo.services import (
    ATTR_HDMI_OUTPUT,
    SERVICE_SELECT_HDMI_OUTPUT,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_ENTITY_PICTURE,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    STATE_IDLE,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import DISCONNECT, receive_messages, setup_integration

ENTITY_ID = "media_player.tx_nr7100"
ENTITY_ID_ZONE_2 = "media_player.tx_nr7100_zone_2"
ENTITY_ID_ZONE_3 = "media_player.tx_nr7100_zone_3"


@pytest.fixture(autouse=True)
async def auto_setup_integration(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_receiver: AsyncMock,
    writes: list[Instruction],
) -> AsyncGenerator[None]:
    """Auto setup integration."""
    with patch("homeassistant.components.onkyo.PLATFORMS", [Platform.MEDIA_PLAYER]):
        await setup_integration(hass, mock_config_entry)

        # Let the delayed queries triggered by the initial messages run
        freezer.tick(timedelta(seconds=max(QUERY_STATE_DELAY, QUERY_AV_INFO_DELAY)))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        writes.clear()
        yield


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_availability(hass: HomeAssistant, read_queue: asyncio.Queue) -> None:
    """Test entity availability on disconnect and reconnect."""
    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert state.state != STATE_UNAVAILABLE

    await receive_messages(read_queue, DISCONNECT)

    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert state.state == STATE_UNAVAILABLE

    # Simulate first status update after reconnect
    await receive_messages(
        read_queue,
        status.Power(
            Code.from_kind_zone(Kind.POWER, Zone.MAIN), None, status.Power.Param.ON
        ),
    )

    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("action", "action_data", "message"),
    [
        (SERVICE_TURN_ON, {}, command.Power(Zone.MAIN, command.Power.Param.ON)),
        (SERVICE_TURN_OFF, {}, command.Power(Zone.MAIN, command.Power.Param.STANDBY)),
        (
            SERVICE_VOLUME_SET,
            {ATTR_MEDIA_VOLUME_LEVEL: 0.5},
            command.Volume(Zone.MAIN, 40),
        ),
        (SERVICE_VOLUME_UP, {}, command.Volume(Zone.MAIN, command.Volume.Param.UP)),
        (SERVICE_VOLUME_DOWN, {}, command.Volume(Zone.MAIN, command.Volume.Param.DOWN)),
        (
            SERVICE_VOLUME_MUTE,
            {ATTR_MEDIA_VOLUME_MUTED: True},
            command.Muting(Zone.MAIN, command.Muting.Param.ON),
        ),
        (
            SERVICE_VOLUME_MUTE,
            {ATTR_MEDIA_VOLUME_MUTED: False},
            command.Muting(Zone.MAIN, command.Muting.Param.OFF),
        ),
    ],
)
async def test_actions(
    hass: HomeAssistant,
    writes: list[Instruction],
    action: str,
    action_data: dict,
    message: Instruction,
) -> None:
    """Test actions."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        action,
        {ATTR_ENTITY_ID: ENTITY_ID, **action_data},
        blocking=True,
    )
    assert writes[0] == message


async def test_select_source(hass: HomeAssistant, writes: list[Instruction]) -> None:
    """Test select source."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "TV"},
        blocking=True,
    )
    assert writes[0] == command.InputSource(Zone.MAIN, command.InputSource.Param("12"))

    writes.clear()
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "InvalidSource"},
            blocking=True,
        )
    assert not writes


async def test_select_sound_mode(
    hass: HomeAssistant, writes: list[Instruction]
) -> None:
    """Test select sound mode."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOUND_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SOUND_MODE: "THX"},
        blocking=True,
    )
    assert writes[0] == command.ListeningMode(
        Zone.MAIN, command.ListeningMode.Param("04")
    )

    writes.clear()
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOUND_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SOUND_MODE: "InvalidMode"},
            blocking=True,
        )
    assert not writes


async def test_play_media(hass: HomeAssistant, writes: list[Instruction]) -> None:
    """Test play media (radio preset)."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: "radio",
            ATTR_MEDIA_CONTENT_ID: "5",
        },
        blocking=True,
    )
    assert writes[0] == command.TunerPreset(Zone.MAIN, 5)

    writes.clear()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: "music",
            ATTR_MEDIA_CONTENT_ID: "5",
        },
        blocking=True,
    )
    assert not writes

    writes.clear()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID_ZONE_2,
            ATTR_MEDIA_CONTENT_TYPE: "radio",
            ATTR_MEDIA_CONTENT_ID: "5",
        },
        blocking=True,
    )
    assert not writes

    writes.clear()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID_ZONE_3,
            ATTR_MEDIA_CONTENT_TYPE: "radio",
            ATTR_MEDIA_CONTENT_ID: "5",
        },
        blocking=True,
    )
    assert not writes


async def test_select_hdmi_output(
    hass: HomeAssistant, writes: list[Instruction]
) -> None:
    """Test select hdmi output."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_HDMI_OUTPUT,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HDMI_OUTPUT: "sub"},
        blocking=True,
    )
    assert writes[0] == command.HDMIOutput(command.HDMIOutput.Param.BOTH)


async def test_query_state_delayed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    read_queue: asyncio.Queue,
    writes: list[Instruction],
) -> None:
    """Test state query."""
    power_standby = status.Power(
        Code.from_kind_zone(Kind.POWER, Zone.MAIN), None, status.Power.Param.STANDBY
    )
    power_on = status.Power(
        Code.from_kind_zone(Kind.POWER, Zone.MAIN), None, status.Power.Param.ON
    )

    await receive_messages(read_queue, power_standby, power_on)

    freezer.tick(timedelta(seconds=QUERY_STATE_DELAY / 2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Powering on again restarts the delay
    await receive_messages(read_queue, power_standby, power_on)

    freezer.tick(timedelta(seconds=QUERY_STATE_DELAY / 2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    queries = [w for w in writes if isinstance(w, query.Volume)]
    assert not queries

    freezer.tick(timedelta(seconds=QUERY_STATE_DELAY / 2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    queries = [w for w in writes if isinstance(w, query.Volume)]
    assert len(queries) == 1


async def test_query_av_info_delayed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    read_queue: asyncio.Queue,
    writes: list[Instruction],
) -> None:
    """Test AV info query."""
    await receive_messages(
        read_queue,
        status.InputSource(
            Code.from_kind_zone(Kind.INPUT_SOURCE, Zone.MAIN),
            None,
            status.InputSource.Param("24"),
        ),
    )

    freezer.tick(timedelta(seconds=QUERY_AV_INFO_DELAY / 2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Another source change while a query is pending does not restart the delay
    await receive_messages(
        read_queue,
        status.InputSource(
            Code.from_kind_zone(Kind.INPUT_SOURCE, Zone.MAIN),
            None,
            status.InputSource.Param("00"),
        ),
    )

    freezer.tick(timedelta(seconds=QUERY_AV_INFO_DELAY / 2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    queries = [w for w in writes if isinstance(w, query.AudioInformation)]
    assert len(queries) == 1


NET_FEATURES = (
    MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
)


def _input_source(source: str) -> status.InputSource:
    return status.InputSource(
        Code.from_kind_zone(Kind.INPUT_SOURCE, Zone.MAIN),
        None,
        status.InputSource.Param(source),
    )


def _net_play_status(playback: NetPlaybackState) -> status.NetPlayStatus:
    return status.NetPlayStatus(
        Code.from_kind_zone(Kind.NET_PLAY_STATUS, Zone.MAIN),
        None,
        playback,
        NetRepeatMode.OFF,
        NetShuffleMode.OFF,
    )


def _net_time(position: int | None, duration: int | None) -> status.NetTime:
    return status.NetTime(
        Code.from_kind_zone(Kind.NET_TIME, Zone.MAIN), None, position, duration
    )


ART_URL = "http://192.168.1.2/album_art.cgi"


def _net_jacket_art(url: str | None) -> status.NetJacketArt:
    code = Code.from_kind_zone(Kind.NET_JACKET_ART, Zone.MAIN)
    if url is None:
        return status.NetJacketArt(
            code, None, NetArtType.NONE, NetArtPacket.SINGLE, b""
        )
    return status.NetJacketArt(
        code, None, NetArtType.URL, NetArtPacket.SINGLE, url.encode()
    )


NET_TRACK_MESSAGES: list[Status] = [
    _net_play_status(NetPlaybackState.PLAYING),
    status.NetTitle(Code.from_kind_zone(Kind.NET_TITLE, Zone.MAIN), None, "Title"),
    status.NetArtist(Code.from_kind_zone(Kind.NET_ARTIST, Zone.MAIN), None, "Artist"),
    status.NetAlbum(Code.from_kind_zone(Kind.NET_ALBUM, Zone.MAIN), None, "Album"),
    status.NetTrack(Code.from_kind_zone(Kind.NET_TRACK, Zone.MAIN), None, 3, 12),
    _net_time(10, 200),
]


async def _select_net_source(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, read_queue: asyncio.Queue
) -> None:
    await receive_messages(read_queue, _input_source("2B"))
    freezer.tick(timedelta(seconds=QUERY_NET_DELAY))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_net_playback(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    read_queue: asyncio.Queue,
    writes: list[Instruction],
) -> None:
    """Test the NET/USB player state on the main zone."""
    await _select_net_source(hass, freezer, read_queue)

    assert [w for w in writes if w.kind.name.startswith("NET_")] == [
        query.NetPlayStatus(),
        query.NetTitle(),
        query.NetArtist(),
        query.NetAlbum(),
        query.NetTrack(),
        query.NetTime(),
        query.NetJacketArt(),
    ]

    await receive_messages(read_queue, *NET_TRACK_MESSAGES)

    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert state.state == STATE_PLAYING
    assert state.attributes[ATTR_SUPPORTED_FEATURES] & NET_FEATURES == NET_FEATURES
    assert state.attributes[ATTR_MEDIA_CONTENT_TYPE] == MediaType.MUSIC
    assert state.attributes[ATTR_MEDIA_TITLE] == "Title"
    assert state.attributes[ATTR_MEDIA_ARTIST] == "Artist"
    assert state.attributes[ATTR_MEDIA_ALBUM_NAME] == "Album"
    assert state.attributes[ATTR_MEDIA_TRACK] == 3
    assert state.attributes[ATTR_MEDIA_DURATION] == 200
    assert state.attributes[ATTR_MEDIA_POSITION] == 10

    await receive_messages(read_queue, _net_play_status(NetPlaybackState.PAUSED))
    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert state.state == STATE_PAUSED

    await receive_messages(read_queue, _net_play_status(NetPlaybackState.STOPPED))
    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert state.state == STATE_IDLE


async def test_net_position(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    read_queue: asyncio.Queue,
) -> None:
    """Test only a jump in the reported position is written."""
    await _select_net_source(hass, freezer, read_queue)
    await receive_messages(read_queue, *NET_TRACK_MESSAGES)

    assert (state := hass.states.get(ENTITY_ID)) is not None
    updated_at = state.attributes[ATTR_MEDIA_POSITION_UPDATED_AT]

    # The receiver reports every second while playing
    freezer.tick(timedelta(seconds=1))
    await receive_messages(read_queue, _net_time(11, 200))
    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert state.attributes[ATTR_MEDIA_POSITION] == 10
    assert state.attributes[ATTR_MEDIA_POSITION_UPDATED_AT] == updated_at

    # A seek on the receiver moves the position
    freezer.tick(timedelta(seconds=1))
    await receive_messages(read_queue, _net_time(100, 200))
    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert state.attributes[ATTR_MEDIA_POSITION] == 100
    assert state.attributes[ATTR_MEDIA_POSITION_UPDATED_AT] != updated_at

    # Pausing anchors the position where playback stopped
    freezer.tick(timedelta(seconds=5))
    await receive_messages(read_queue, _net_play_status(NetPlaybackState.PAUSED))
    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert state.attributes[ATTR_MEDIA_POSITION] == 105

    freezer.tick(timedelta(seconds=5))
    await receive_messages(read_queue, _net_time(105, 200))
    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert state.attributes[ATTR_MEDIA_POSITION] == 105


@pytest.mark.parametrize(
    ("action", "param"),
    [
        (SERVICE_MEDIA_PLAY, command.NetOperation.Param.PLAY),
        (SERVICE_MEDIA_PAUSE, command.NetOperation.Param.PAUSE),
        (SERVICE_MEDIA_STOP, command.NetOperation.Param.STOP),
        (SERVICE_MEDIA_NEXT_TRACK, command.NetOperation.Param.NEXT),
        (SERVICE_MEDIA_PREVIOUS_TRACK, command.NetOperation.Param.PREVIOUS),
    ],
)
async def test_net_actions(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    read_queue: asyncio.Queue,
    writes: list[Instruction],
    action: str,
    param: command.NetOperation.Param,
) -> None:
    """Test the transport actions."""
    await _select_net_source(hass, freezer, read_queue)
    await receive_messages(read_queue, *NET_TRACK_MESSAGES)
    writes.clear()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, action, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    assert writes == [command.NetOperation(param)]


@pytest.mark.parametrize(
    "messages",
    [
        pytest.param([_input_source("24")], id="source_change"),
        pytest.param(
            [
                status.Power(
                    Code.from_kind_zone(Kind.POWER, Zone.MAIN),
                    None,
                    status.Power.Param.STANDBY,
                ),
                status.Power(
                    Code.from_kind_zone(Kind.POWER, Zone.MAIN),
                    None,
                    status.Power.Param.ON,
                ),
            ],
            id="standby",
        ),
    ],
)
async def test_net_playback_cleared(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    read_queue: asyncio.Queue,
    messages: list[Status],
) -> None:
    """Test leaving the NET source or standby clears the player state."""
    await _select_net_source(hass, freezer, read_queue)
    await receive_messages(read_queue, *NET_TRACK_MESSAGES, *messages)

    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert state.state == STATE_ON
    assert not state.attributes[ATTR_SUPPORTED_FEATURES] & NET_FEATURES
    assert ATTR_MEDIA_TITLE not in state.attributes
    assert ATTR_MEDIA_POSITION not in state.attributes


async def test_net_input_switch(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    read_queue: asyncio.Queue,
    writes: list[Instruction],
) -> None:
    """Test switching between NET/USB inputs clears and queries again."""
    await _select_net_source(hass, freezer, read_queue)
    await receive_messages(read_queue, *NET_TRACK_MESSAGES)
    writes.clear()

    # A repeated report of the same input keeps the state
    await receive_messages(read_queue, _input_source("2B"))
    freezer.tick(timedelta(seconds=QUERY_NET_DELAY))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert query.NetPlayStatus() not in writes
    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert state.state == STATE_PLAYING
    assert state.attributes[ATTR_MEDIA_TITLE] == "Title"

    # Switching from NETWORK to USB drops the old track
    await receive_messages(read_queue, _input_source("29"))
    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert state.state == STATE_ON
    assert ATTR_MEDIA_TITLE not in state.attributes
    assert not state.attributes[ATTR_SUPPORTED_FEATURES] & NET_FEATURES

    freezer.tick(timedelta(seconds=QUERY_NET_DELAY))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert query.NetPlayStatus() in writes


async def test_net_input_switch_restarts_query_delay(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    read_queue: asyncio.Queue,
    writes: list[Instruction],
) -> None:
    """Test a second input change before the query restarts its delay."""
    await receive_messages(read_queue, _input_source("2B"))
    freezer.tick(timedelta(seconds=QUERY_NET_DELAY / 2))
    async_fire_time_changed_exact(hass)
    await hass.async_block_till_done()

    await receive_messages(read_queue, _input_source("29"))
    freezer.tick(timedelta(seconds=QUERY_NET_DELAY / 2))
    async_fire_time_changed_exact(hass)
    await hass.async_block_till_done()
    assert query.NetPlayStatus() not in writes

    freezer.tick(timedelta(seconds=QUERY_NET_DELAY / 2))
    async_fire_time_changed_exact(hass)
    await hass.async_block_till_done()
    assert writes.count(query.NetPlayStatus()) == 1


async def test_net_status_ignored_on_other_source(
    hass: HomeAssistant, read_queue: asyncio.Queue
) -> None:
    """Test NET reports do not change the state on another input."""
    await receive_messages(read_queue, *NET_TRACK_MESSAGES)

    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert state.state == STATE_ON
    assert ATTR_MEDIA_TITLE not in state.attributes


async def test_net_playback_cleared_on_disconnect(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    read_queue: asyncio.Queue,
    writes: list[Instruction],
) -> None:
    """Test a reconnect queries the NET player again."""
    await _select_net_source(hass, freezer, read_queue)
    await receive_messages(read_queue, *NET_TRACK_MESSAGES, DISCONNECT)
    writes.clear()

    await _select_net_source(hass, freezer, read_queue)
    assert query.NetPlayStatus() in writes
    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert ATTR_MEDIA_TITLE not in state.attributes


async def test_net_cover_art(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    read_queue: asyncio.Queue,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the cover art the receiver serves on its own address."""
    await _select_net_source(hass, freezer, read_queue)
    await receive_messages(read_queue, *NET_TRACK_MESSAGES)

    # No art yet, and an unrecognized report (such as "LINK") changes nothing
    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert ATTR_ENTITY_PICTURE not in state.attributes

    await receive_messages(read_queue, _net_jacket_art(ART_URL))
    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert ATTR_ENTITY_PICTURE in state.attributes
    first_picture = state.attributes[ATTR_ENTITY_PICTURE]

    # The receiver puts header lines in front of the image, they are removed
    image = b"\xff\xd8\xff\xd9"
    aioclient_mock.get(
        ART_URL,
        content=b"Content-size: 4\nContent-type: image/jpeg\n\n" + image,
    )
    player = hass.data[DATA_COMPONENT].get_entity(ENTITY_ID)
    assert await player.async_get_media_image() == (image, "image/jpeg")

    # A new track with new art changes the picture address, so the old image is not reused
    await receive_messages(read_queue, _net_jacket_art(ART_URL))
    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert state.attributes[ATTR_ENTITY_PICTURE] != first_picture

    await receive_messages(read_queue, _net_jacket_art(None))
    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert ATTR_ENTITY_PICTURE not in state.attributes


@pytest.mark.parametrize(
    "preamble",
    [
        b"Content-size: 4\nContent-type: image/png\n\n",
        b"Content-size: 4\r\nContent-type: image/png\r\n\r\n",
        b"content-size: 4\r\nCONTENT-TYPE: image/png\r\n\r\n",
        b"Content-size: 4\nContent-type: image/png; charset=UTF-8\n\n",
    ],
    ids=["lf", "crlf", "mixed_case", "parameters"],
)
async def test_net_cover_art_preamble(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    read_queue: asyncio.Queue,
    aioclient_mock: AiohttpClientMocker,
    preamble: bytes,
) -> None:
    """Test that the header lines are removed with either line ending."""
    await _select_net_source(hass, freezer, read_queue)
    await receive_messages(read_queue, *NET_TRACK_MESSAGES, _net_jacket_art(ART_URL))

    image = b"\x89PNG"
    aioclient_mock.get(ART_URL, content=preamble + image)
    player = hass.data[DATA_COMPONENT].get_entity(ENTITY_ID)
    assert await player.async_get_media_image() == (image, "image/png")


async def test_net_cover_art_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    read_queue: asyncio.Queue,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that no image is returned when the receiver cannot be reached."""
    await _select_net_source(hass, freezer, read_queue)
    await receive_messages(read_queue, *NET_TRACK_MESSAGES, _net_jacket_art(ART_URL))

    aioclient_mock.get(ART_URL, exc=TimeoutError)
    player = hass.data[DATA_COMPONENT].get_entity(ENTITY_ID)
    assert await player.async_get_media_image() == (None, None)


@pytest.mark.parametrize(
    "content",
    [
        b"Content-size: 4\nContent-type: image/jpeg\n\n\xff\xd8",
        b"Content-size: many\nContent-type: image/jpeg\n\n\xff\xd8\xff\xd9",
        b"Content-size: 0\nContent-type: image/jpeg\n\n",
        b"",
    ],
    ids=["short", "invalid_size", "empty_image", "empty_response"],
)
async def test_net_cover_art_truncated(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    read_queue: asyncio.Queue,
    aioclient_mock: AiohttpClientMocker,
    content: bytes,
) -> None:
    """Test that an empty image, or one shorter than its stated size, is not kept."""
    await _select_net_source(hass, freezer, read_queue)
    await receive_messages(read_queue, *NET_TRACK_MESSAGES, _net_jacket_art(ART_URL))

    aioclient_mock.get(ART_URL, content=content)
    player = hass.data[DATA_COMPONENT].get_entity(ENTITY_ID)
    assert await player.async_get_media_image() == (None, None)
    assert aioclient_mock.call_count == 1

    # The next request tries the receiver again
    assert await player.async_get_media_image() == (None, None)
    assert aioclient_mock.call_count == 2


async def test_net_cover_art_cached(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    read_queue: asyncio.Queue,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the cover art is fetched again only for a new track or art report."""
    await _select_net_source(hass, freezer, read_queue)
    await receive_messages(read_queue, *NET_TRACK_MESSAGES, _net_jacket_art(ART_URL))
    player = hass.data[DATA_COMPONENT].get_entity(ENTITY_ID)

    # A failed fetch is not kept
    aioclient_mock.get(ART_URL, exc=TimeoutError)
    assert await player.async_get_media_image() == (None, None)
    assert aioclient_mock.call_count == 1

    aioclient_mock.clear_requests()
    image = b"\xff\xd8\xff\xd9"
    aioclient_mock.get(
        ART_URL,
        content=b"Content-size: 4\nContent-type: image/jpeg\n\n" + image,
    )
    assert await player.async_get_media_image() == (image, "image/jpeg")
    assert aioclient_mock.call_count == 1

    # The same track reuses the image
    assert await player.async_get_media_image() == (image, "image/jpeg")
    assert aioclient_mock.call_count == 1

    # A new title fetches it again
    await receive_messages(
        read_queue,
        status.NetTitle(Code.from_kind_zone(Kind.NET_TITLE, Zone.MAIN), None, "Next"),
    )
    assert await player.async_get_media_image() == (image, "image/jpeg")
    assert aioclient_mock.call_count == 2

    # So does a new art report for the same track
    await receive_messages(read_queue, _net_jacket_art(ART_URL))
    assert await player.async_get_media_image() == (image, "image/jpeg")
    assert aioclient_mock.call_count == 3
    assert await player.async_get_media_image() == (image, "image/jpeg")
    assert aioclient_mock.call_count == 3
