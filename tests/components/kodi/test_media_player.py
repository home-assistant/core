"""Tests for the Kodi media player."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from jsonrpc_base.jsonrpc import TransportError
from pykodi import CannotConnectError
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.kodi.const import DOMAIN
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_POSITION_UPDATED_AT,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    SCAN_INTERVAL,
    MediaPlayerState,
    MediaType,
)
from homeassistant.const import (
    ATTR_ENTITY_PICTURE,
    EVENT_HOMEASSISTANT_STARTED,
    STATE_UNAVAILABLE,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from . import AUDIO_PLAYER, VIDEO_PLAYER, set_idle, set_playing, setup_integration
from .util import UUID

from tests.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
    async_load_json_object_fixture,
    snapshot_platform,
)

ENTITY_ID = "media_player.name"
ATTR_DYNAMIC_RANGE = "dynamic_range"

WATCHDOG_INTERVAL = timedelta(seconds=10)

websocket = pytest.mark.parametrize(
    "can_subscribe", [pytest.param(True, id="websocket")]
)


def player_notification(speed: int) -> dict[str, Any]:
    """Return the data of a Kodi player notification."""
    return {
        "item": {"id": 1, "type": "movie"},
        "player": {"playerid": 1, "speed": speed},
    }


async def advance_time(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, interval: timedelta
) -> None:
    """Let the given time pass."""
    freezer.tick(interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def start_home_assistant(hass: HomeAssistant) -> None:
    """Announce that Home Assistant has started."""
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()


async def pass_watchdog_interval(hass: HomeAssistant) -> None:
    """Let the watchdog interval pass."""
    async_fire_time_changed(hass, dt_util.utcnow() + WATCHDOG_INTERVAL)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_connection", "mock_kodi")
@pytest.mark.parametrize(
    "unique_id",
    [pytest.param(UUID, id="unique_id"), pytest.param(None, id="no_unique_id")],
)
async def test_entity_and_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the registered entity and device."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert devices == snapshot(name="devices")


@pytest.mark.usefixtures("mock_connection")
@pytest.mark.parametrize(
    ("speed", "expected_state"),
    [
        pytest.param(0, MediaPlayerState.PAUSED, id="paused"),
        pytest.param(1, MediaPlayerState.PLAYING, id="playing"),
    ],
)
async def test_polled_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_kodi: MagicMock,
    freezer: FrozenDateTimeFactory,
    speed: int,
    expected_state: MediaPlayerState,
) -> None:
    """Test the state derived from the polled playback speed."""
    await set_playing(hass, mock_kodi, speed=speed)
    await setup_integration(hass, mock_config_entry)

    await advance_time(hass, freezer, SCAN_INTERVAL)

    assert hass.states.get(ENTITY_ID).state == expected_state


@pytest.mark.parametrize(
    ("connected", "get_players"),
    [
        pytest.param(False, {"return_value": [VIDEO_PLAYER]}, id="not_connected"),
        pytest.param(
            True,
            {"side_effect": TransportError("Connection lost")},
            id="request_failed",
        ),
        pytest.param(True, {"return_value": None}, id="players_unavailable"),
    ],
)
async def test_polled_state_turns_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_kodi: MagicMock,
    freezer: FrozenDateTimeFactory,
    connected: bool,
    get_players: dict[str, Any],
) -> None:
    """Test losing Kodi while polling turns the state off."""
    await set_playing(hass, mock_kodi)
    await setup_integration(hass, mock_config_entry)
    await advance_time(hass, freezer, SCAN_INTERVAL)
    assert hass.states.get(ENTITY_ID).state == MediaPlayerState.PLAYING

    mock_connection.connected = connected
    mock_kodi.get_players.configure_mock(**get_players)
    await advance_time(hass, freezer, SCAN_INTERVAL)

    state = hass.states.get(ENTITY_ID)
    assert state.state == MediaPlayerState.OFF
    assert ATTR_MEDIA_TITLE not in state.attributes


@pytest.mark.usefixtures("mock_connection")
@pytest.mark.freeze_time("2026-01-01 12:00:00+00:00")
@pytest.mark.parametrize(
    ("players", "fixture", "properties"),
    [
        pytest.param([VIDEO_PLAYER], "movie.json", {}, id="movie"),
        pytest.param([VIDEO_PLAYER], "episode.json", {}, id="episode"),
        pytest.param([AUDIO_PLAYER], "song.json", {}, id="song"),
        pytest.param([VIDEO_PLAYER], "channel.json", {"live": True}, id="live_channel"),
        pytest.param(
            [VIDEO_PLAYER, AUDIO_PLAYER], "movie.json", {}, id="first_of_two_players"
        ),
    ],
)
async def test_state_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_kodi: MagicMock,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    players: list[dict[str, Any]],
    fixture: str,
    properties: dict[str, Any],
) -> None:
    """Test the state attributes for each kind of playing item."""
    item = await async_load_json_object_fixture(hass, fixture, DOMAIN)
    await set_playing(hass, mock_kodi, item, players, **properties)
    await setup_integration(hass, mock_config_entry)

    await advance_time(hass, freezer, SCAN_INTERVAL)

    # The entity picture contains a random access token
    assert hass.states.get(ENTITY_ID) == snapshot(exclude=props(ATTR_ENTITY_PICTURE))


@pytest.mark.usefixtures("mock_connection", "mock_kodi")
async def test_idle_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the state and attributes while nothing is playing."""
    await setup_integration(hass, mock_config_entry)

    await advance_time(hass, freezer, SCAN_INTERVAL)

    assert hass.states.get(ENTITY_ID) == snapshot


@pytest.mark.usefixtures("mock_connection")
@pytest.mark.parametrize(
    ("item", "expected_title"),
    [
        pytest.param(
            {"title": "Title", "label": "Label", "file": "/movie.mkv"},
            "Title",
            id="title",
        ),
        pytest.param(
            {"title": "", "label": "Label", "file": "/movie.mkv"},
            "Label",
            id="label",
        ),
        pytest.param(
            {"title": "", "label": "", "file": "/movie.mkv"},
            "/movie.mkv",
            id="file",
        ),
    ],
)
async def test_media_title_fallback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_kodi: MagicMock,
    freezer: FrozenDateTimeFactory,
    item: dict[str, Any],
    expected_title: str,
) -> None:
    """Test the media title falls back to the label and then the file."""
    await set_playing(hass, mock_kodi, item)
    await setup_integration(hass, mock_config_entry)

    await advance_time(hass, freezer, SCAN_INTERVAL)

    assert hass.states.get(ENTITY_ID).attributes[ATTR_MEDIA_TITLE] == expected_title


@pytest.mark.usefixtures("mock_connection")
@pytest.mark.parametrize(
    ("players", "item_type", "expected_content_type"),
    [
        pytest.param([VIDEO_PLAYER], "episode", MediaType.TVSHOW, id="known_type"),
        pytest.param([VIDEO_PLAYER], "unknown", MediaType.VIDEO, id="unknown_video"),
        pytest.param([AUDIO_PLAYER], "unknown", MediaType.MUSIC, id="unknown_audio"),
        pytest.param([VIDEO_PLAYER], "channel", MediaType.VIDEO, id="tv_channel"),
        pytest.param([AUDIO_PLAYER], "channel", MediaType.MUSIC, id="radio_channel"),
        pytest.param(
            [VIDEO_PLAYER, AUDIO_PLAYER],
            "unknown",
            MediaType.VIDEO,
            id="first_of_two_players",
        ),
    ],
)
async def test_media_content_type(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_kodi: MagicMock,
    freezer: FrozenDateTimeFactory,
    players: list[dict[str, Any]],
    item_type: str,
    expected_content_type: MediaType,
) -> None:
    """Test unknown and channel items use the type of the active player."""
    await set_playing(hass, mock_kodi, {"type": item_type, "label": "Label"}, players)
    await setup_integration(hass, mock_config_entry)

    await advance_time(hass, freezer, SCAN_INTERVAL)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_MEDIA_CONTENT_TYPE] == expected_content_type


@pytest.mark.usefixtures("mock_connection")
async def test_media_position_updated_at(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_kodi: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the position timestamp only moves when the position changes."""
    await set_playing(hass, mock_kodi)
    await setup_integration(hass, mock_config_entry)

    await advance_time(hass, freezer, SCAN_INTERVAL)
    first_update = dt_util.utcnow()
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_MEDIA_POSITION] == 4205
    assert state.attributes[ATTR_MEDIA_POSITION_UPDATED_AT] == first_update

    await advance_time(hass, freezer, SCAN_INTERVAL)
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_MEDIA_POSITION_UPDATED_AT] == first_update

    await set_playing(
        hass,
        mock_kodi,
        time={"hours": 1, "minutes": 11, "seconds": 0, "milliseconds": 71},
    )
    await advance_time(hass, freezer, SCAN_INTERVAL)
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_MEDIA_POSITION] == 4260
    assert state.attributes[ATTR_MEDIA_POSITION_UPDATED_AT] == dt_util.utcnow()


@pytest.mark.usefixtures("mock_connection")
async def test_media_position_updated_at_after_idle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_kodi: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the position timestamp is set again after playback was stopped."""
    await set_playing(hass, mock_kodi)
    await setup_integration(hass, mock_config_entry)
    await advance_time(hass, freezer, SCAN_INTERVAL)

    set_idle(mock_kodi)
    await advance_time(hass, freezer, SCAN_INTERVAL)
    state = hass.states.get(ENTITY_ID)
    assert state.state == MediaPlayerState.IDLE
    assert ATTR_MEDIA_POSITION_UPDATED_AT not in state.attributes

    await set_playing(hass, mock_kodi)
    await advance_time(hass, freezer, SCAN_INTERVAL)
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_MEDIA_POSITION] == 4205
    assert state.attributes[ATTR_MEDIA_POSITION_UPDATED_AT] == dt_util.utcnow()


@pytest.mark.usefixtures("mock_connection")
async def test_entity_picture(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_kodi: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the thumbnail of the playing item is exposed as entity picture."""
    await set_playing(
        hass, mock_kodi, {"label": "Movie", "thumbnail": "image://movie.jpg/"}
    )
    await setup_integration(hass, mock_config_entry)

    await advance_time(hass, freezer, SCAN_INTERVAL)

    assert ATTR_ENTITY_PICTURE in hass.states.get(ENTITY_ID).attributes
    mock_kodi.thumbnail_url.assert_called_with("image://movie.jpg/")


@pytest.mark.usefixtures("mock_connection")
@pytest.mark.parametrize(
    ("item", "expected_dynamic_range"),
    [
        pytest.param({"label": "Label"}, "sdr", id="no_streamdetails"),
        pytest.param(
            {"streamdetails": {"video": [{"hdrtype": ""}]}},
            "sdr",
            id="empty_hdrtype",
        ),
        pytest.param(
            {"streamdetails": {"video": [{"hdrtype": "hdr10"}]}},
            "hdr10",
            id="hdr10",
        ),
        pytest.param(
            {"streamdetails": {"video": [{"hdrtype": "hlg"}, {"hdrtype": "hdr10"}]}},
            "hlg",
            id="first_of_two_streams",
        ),
    ],
)
async def test_dynamic_range(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_kodi: MagicMock,
    freezer: FrozenDateTimeFactory,
    item: dict[str, Any],
    expected_dynamic_range: str,
) -> None:
    """Test the dynamic range attribute follows the video stream details."""
    await set_playing(hass, mock_kodi, item)
    await setup_integration(hass, mock_config_entry)

    await advance_time(hass, freezer, SCAN_INTERVAL)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_DYNAMIC_RANGE] == expected_dynamic_range


@pytest.mark.usefixtures("mock_kodi")
async def test_no_dynamic_range_when_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the dynamic range attribute is not set while Kodi is off."""
    mock_connection.connected = False
    await setup_integration(hass, mock_config_entry)

    await advance_time(hass, freezer, SCAN_INTERVAL)

    state = hass.states.get(ENTITY_ID)
    assert state.state == MediaPlayerState.OFF
    assert ATTR_DYNAMIC_RANGE not in state.attributes


@websocket
async def test_websocket_setup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_kodi: MagicMock,
) -> None:
    """Test a connected websocket refreshes the state and the device."""
    await set_playing(hass, mock_kodi)

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID).state == MediaPlayerState.PLAYING
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.unique_id), mock_config_entry.entry_id
    )
    assert device.sw_version == "21.2"


@websocket
@pytest.mark.usefixtures("mock_connection")
async def test_websocket_does_not_poll(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_kodi: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the state is only refreshed by notifications over the websocket."""
    await setup_integration(hass, mock_config_entry)
    mock_kodi.get_players.reset_mock()

    await advance_time(hass, freezer, SCAN_INTERVAL)

    mock_kodi.get_players.assert_not_awaited()


@websocket
@pytest.mark.parametrize(
    ("notification", "speed", "expected_state"),
    [
        pytest.param("OnPlay", 1, MediaPlayerState.PLAYING, id="play"),
        pytest.param("OnPause", 0, MediaPlayerState.PAUSED, id="pause"),
        pytest.param("OnResume", 1, MediaPlayerState.PLAYING, id="resume"),
        pytest.param("OnAVStart", 1, MediaPlayerState.PLAYING, id="av_start"),
        pytest.param("OnAVChange", 1, MediaPlayerState.PLAYING, id="av_change"),
        pytest.param("OnSeek", 1, MediaPlayerState.PLAYING, id="seek"),
        pytest.param("OnSpeedChanged", 2, MediaPlayerState.PLAYING, id="speed_changed"),
    ],
)
async def test_websocket_player_notification(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_kodi: MagicMock,
    notification: str,
    speed: int,
    expected_state: MediaPlayerState,
) -> None:
    """Test player notifications refresh the state from Kodi."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state == MediaPlayerState.IDLE
    await set_playing(hass, mock_kodi, speed=speed)

    getattr(mock_connection.server.Player, notification)(
        "xbmc", player_notification(speed)
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == expected_state
    assert state.attributes[ATTR_MEDIA_TITLE] == "Movie title"


@websocket
async def test_websocket_refresh_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_kodi: MagicMock,
) -> None:
    """Test a failed refresh keeps the state reported by the notification."""
    await set_playing(hass, mock_kodi)
    await setup_integration(hass, mock_config_entry)
    mock_kodi.get_players.side_effect = TransportError("Connection lost")

    mock_connection.server.Player.OnPause("xbmc", player_notification(0))
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == MediaPlayerState.PAUSED


@websocket
async def test_websocket_stop(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_kodi: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the stop notification sets the state to idle without a refresh."""
    await set_playing(hass, mock_kodi)
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state == MediaPlayerState.PLAYING
    mock_kodi.get_players.reset_mock()

    mock_connection.server.Player.OnStop(
        "xbmc", {"end": False, "item": {"id": 1, "type": "movie"}}
    )
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID) == snapshot
    mock_kodi.get_players.assert_not_awaited()


@websocket
async def test_websocket_volume_changed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_kodi: MagicMock,
) -> None:
    """Test the volume notification updates the state without a refresh."""
    await set_playing(hass, mock_kodi)
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.8
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is False
    mock_kodi.get_players.reset_mock()

    mock_connection.server.Application.OnVolumeChanged(
        "xbmc", {"volume": 35, "muted": True}
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.35
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is True
    mock_kodi.get_players.assert_not_awaited()


@websocket
@pytest.mark.usefixtures("mock_kodi")
async def test_websocket_keypress(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test a key press notification is fired as an event."""
    await setup_integration(hass, mock_config_entry)
    events = async_capture_events(hass, f"{DOMAIN}_keypress")

    mock_connection.server.Other.OnKeyPress("KodiLivingroom", {"key": "volume_up"})
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data == {
        "type": "keypress",
        "device_id": entity_registry.async_get(ENTITY_ID).device_id,
        "entity_id": ENTITY_ID,
        "sender": "KodiLivingroom",
        "data": {"key": "volume_up"},
    }


@websocket
@pytest.mark.parametrize("notification", ["OnQuit", "OnRestart", "OnSleep"])
async def test_websocket_system_notification(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_kodi: MagicMock,
    notification: str,
) -> None:
    """Test Kodi going away turns the state off and closes the connection."""
    await set_playing(hass, mock_kodi)
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state == MediaPlayerState.PLAYING

    await getattr(mock_connection.server.System, notification)("xbmc", None)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == MediaPlayerState.OFF
    mock_connection.close.assert_awaited_once()

    mock_connection.server.Player.OnStop(
        "xbmc", {"end": False, "item": {"id": 1, "type": "movie"}}
    )
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == MediaPlayerState.OFF


@websocket
@pytest.mark.parametrize(
    ("core_state", "trigger"),
    [
        pytest.param(
            CoreState.not_running, start_home_assistant, id="home_assistant_started"
        ),
        pytest.param(CoreState.running, pass_watchdog_interval, id="watchdog_interval"),
    ],
)
async def test_watchdog_connects(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_kodi: MagicMock,
    core_state: CoreState,
    trigger: Callable[[HomeAssistant], Awaitable[None]],
) -> None:
    """Test the watchdog connects the websocket and refreshes the state."""

    async def connect() -> None:
        mock_connection.connected = True

    hass.set_state(core_state)
    mock_connection.connected = False
    mock_connection.connect.side_effect = CannotConnectError
    await set_playing(hass, mock_kodi)
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state == MediaPlayerState.OFF
    mock_connection.connect.side_effect = connect

    await trigger(hass)

    assert hass.states.get(ENTITY_ID).state == MediaPlayerState.PLAYING


@websocket
async def test_watchdog_ping_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_kodi: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failed ping turns the state off and warns only once."""
    await set_playing(hass, mock_kodi)
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state == MediaPlayerState.PLAYING
    mock_kodi.ping.side_effect = TransportError("Connection lost")

    await advance_time(hass, freezer, WATCHDOG_INTERVAL)

    assert hass.states.get(ENTITY_ID).state == MediaPlayerState.OFF
    mock_connection.close.assert_awaited_once()

    await advance_time(hass, freezer, WATCHDOG_INTERVAL)

    assert caplog.text.count("Unable to ping Kodi via websocket") == 1


@websocket
@pytest.mark.usefixtures("mock_kodi")
async def test_watchdog_connect_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failed reconnect keeps the state off and warns only once."""
    mock_connection.connected = False
    mock_connection.connect.side_effect = CannotConnectError
    await setup_integration(hass, mock_config_entry)

    await advance_time(hass, freezer, WATCHDOG_INTERVAL)

    assert hass.states.get(ENTITY_ID).state == MediaPlayerState.OFF
    assert caplog.text.count("Unable to connect to Kodi via websocket") == 1
    mock_connection.close.assert_not_awaited()


@websocket
@pytest.mark.usefixtures("mock_connection")
async def test_watchdog_warns_again_after_ping_recovers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_kodi: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a ping failing after a successful ping is reported again."""
    await setup_integration(hass, mock_config_entry)

    mock_kodi.ping.side_effect = TransportError("Connection lost")
    await advance_time(hass, freezer, WATCHDOG_INTERVAL)
    assert caplog.text.count("Unable to ping Kodi via websocket") == 1

    mock_kodi.ping.side_effect = None
    await advance_time(hass, freezer, WATCHDOG_INTERVAL)

    mock_kodi.ping.side_effect = TransportError("Connection lost")
    await advance_time(hass, freezer, WATCHDOG_INTERVAL)
    assert caplog.text.count("Unable to ping Kodi via websocket") == 2


@websocket
@pytest.mark.usefixtures("mock_kodi")
async def test_watchdog_warns_again_after_reconnect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a connection lost after a reconnect is reported again."""

    async def connect() -> None:
        mock_connection.connected = True

    mock_connection.connected = False
    mock_connection.connect.side_effect = CannotConnectError
    await setup_integration(hass, mock_config_entry)
    assert caplog.text.count("Unable to connect to Kodi via websocket") == 1

    mock_connection.connect.side_effect = connect
    await advance_time(hass, freezer, WATCHDOG_INTERVAL)
    assert hass.states.get(ENTITY_ID).state == MediaPlayerState.IDLE

    mock_connection.connected = False
    mock_connection.connect.side_effect = CannotConnectError
    await advance_time(hass, freezer, WATCHDOG_INTERVAL)

    assert hass.states.get(ENTITY_ID).state == MediaPlayerState.OFF
    assert caplog.text.count("Unable to connect to Kodi via websocket") == 2


@websocket
async def test_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
    mock_kodi: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test unloading closes the connection and stops the watchdog."""
    await setup_integration(hass, mock_config_entry)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    mock_connection.close.assert_awaited_once()
    mock_kodi.ping.reset_mock()

    await advance_time(hass, freezer, WATCHDOG_INTERVAL)

    mock_kodi.ping.assert_not_awaited()
