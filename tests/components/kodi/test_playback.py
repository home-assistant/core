"""Tests for Kodi playback entities."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from jsonrpc_base.jsonrpc import ProtocolError, TransportError
from pykodi import CannotConnectError
import pytest

from homeassistant.components.kodi.coordinator import KodiPlaybackCoordinator
from homeassistant.components.kodi.select import KodiTrackSelect
from homeassistant.components.kodi.sensor import SENSORS, KodiStreamSensor
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .util import TEST_IMPORT, UUID, MockConnection

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
def coordinator(hass: HomeAssistant) -> KodiPlaybackCoordinator:
    """Create a playback coordinator."""
    entry = MockConfigEntry(domain="kodi", data={"name": "Kodi"})
    connection = MagicMock(connected=True)
    kodi = MagicMock()
    kodi.get_players = AsyncMock(return_value=[{"playerid": 1, "type": "video"}])
    kodi.get_player_properties = AsyncMock(
        return_value={
            "audiostreams": [{"index": 3, "language": "eng", "name": "Main"}],
            "currentaudiostream": {"index": 3, "codec": "aac", "channels": 2},
            "subtitles": [{"index": 7, "language": "eng", "name": "English"}],
            "currentsubtitle": {"index": 7},
            "subtitleenabled": True,
            "currentvideostream": {"width": 1920, "height": 1080, "codec": "h264"},
        }
    )

    async def call_method(method: str, **kwargs: object) -> object:
        if method == "Settings.GetSettingValue":
            return {
                "value": {
                    "subtitles.align": 2,
                    "subtitles.marginvertical": 6.0,
                    "subtitles.opacity": 80,
                }[kwargs["setting"]]
            }
        if method == "Player.GetViewMode":
            return {"verticalshift": 0.2, "viewmode": "custom"}
        if method == "XBMC.GetInfoLabels":
            return {
                "Player.Process(VideoFPS)": "23.976",
                "VideoPlayer.HdrType": "dolbyvision",
            }
        if method == "Settings.SetSettingValue":
            return True
        return "OK"

    kodi.call_method = AsyncMock(side_effect=call_method)
    return KodiPlaybackCoordinator(hass, entry, connection, kodi)


async def test_tracks(coordinator: KodiPlaybackCoordinator) -> None:
    """Use real stream indexes and refresh after commands."""
    await coordinator.async_refresh()
    audio = KodiTrackSelect(coordinator, "audio")
    subtitle = KodiTrackSelect(coordinator, "subtitle")
    assert audio.options == ["3: eng — Main"]
    assert audio.current_option == audio.options[0]
    assert subtitle.options == ["Off", "7: eng — English"]
    await audio.async_select_option(audio.options[0])
    coordinator.kodi.call_method.assert_any_await(
        "Player.SetAudioStream", playerid=1, stream=3
    )
    await subtitle.async_select_option(subtitle.options[1])
    coordinator.kodi.call_method.assert_any_await(
        "Player.SetSubtitle", playerid=1, subtitle=7, enable=True
    )
    await subtitle.async_select_option("Off")
    coordinator.kodi.call_method.assert_any_await(
        "Player.SetSubtitle", playerid=1, subtitle="off"
    )
    with pytest.raises(ServiceValidationError):
        await audio.async_select_option("stale")


async def test_sensors_and_stop(coordinator: KodiPlaybackCoordinator) -> None:
    """Expose stream data and clear it when playback stops."""
    await coordinator.async_refresh()
    sensors = {
        description.key: KodiStreamSensor(coordinator, description)
        for description in SENSORS
    }
    assert sensors["video_width"].native_value == 1920
    assert sensors["audio_codec"].native_value == "aac"
    assert sensors["video_fps"].native_value == 23.976
    assert sensors["video_hdr_type"].native_value == "Dolby Vision"
    assert sensors["picture_view_mode"].native_value == "custom"
    assert {sensor.key for sensor in SENSORS}.isdisjoint(
        {"audio_bitrate", "audio_sample_rate", "audio_bits_per_sample"}
    )
    coordinator.kodi.get_players.return_value = []
    await coordinator.async_refresh()
    assert not KodiTrackSelect(coordinator, "audio").available
    assert sensors["video_width"].native_value is None


@pytest.mark.parametrize(
    "labels",
    [
        pytest.param({}, id="missing"),
        pytest.param({"VideoPlayer.HdrType": ""}, id="empty"),
        pytest.param({"VideoPlayer.HdrType": None}, id="null"),
    ],
)
async def test_unknown_hdr_type(
    coordinator: KodiPlaybackCoordinator, labels: dict[str, str | None]
) -> None:
    """Unsupported HDR labels must not identify video as SDR."""
    original = coordinator.kodi.call_method.side_effect

    async def call_method(method: str, **kwargs: object) -> object:
        if method == "XBMC.GetInfoLabels":
            return labels
        return await original(method, **kwargs)

    coordinator.kodi.call_method.side_effect = call_method
    await coordinator.async_refresh()
    description = next(item for item in SENSORS if item.key == "video_hdr_type")
    assert KodiStreamSensor(coordinator, description).native_value is None


async def test_ignore_picture_player(coordinator: KodiPlaybackCoordinator) -> None:
    """Pictures do not expose audio and subtitle streams."""
    coordinator.kodi.get_players.return_value = [{"playerid": 2, "type": "picture"}]
    await coordinator.async_refresh()
    coordinator.kodi.get_player_properties.assert_not_awaited()
    assert not KodiTrackSelect(coordinator, "subtitle").available


async def test_disconnect_and_recovery(coordinator: KodiPlaybackCoordinator) -> None:
    """A failed read makes the entities unavailable until the next successful read."""
    await coordinator.async_refresh()
    coordinator.kodi.get_players.side_effect = TransportError("offline")
    await coordinator.async_refresh()
    assert not KodiTrackSelect(coordinator, "audio").available
    coordinator.kodi.get_players.side_effect = None
    await coordinator.async_refresh()
    assert KodiTrackSelect(coordinator, "audio").available


async def test_audio_player(coordinator: KodiPlaybackCoordinator) -> None:
    """Only request audio properties when playing music."""
    player = {"playerid": 0, "type": "audio"}
    coordinator.kodi.get_players.return_value = [player]
    await coordinator.async_refresh()
    coordinator.kodi.get_player_properties.assert_awaited_once_with(
        player, ["currentaudiostream", "audiostreams"]
    )
    assert KodiTrackSelect(coordinator, "audio").available
    assert not KodiTrackSelect(coordinator, "subtitle").available


async def test_prefer_video(coordinator: KodiPlaybackCoordinator) -> None:
    """Video takes precedence over other active players."""
    video = {"playerid": 1, "type": "video"}
    coordinator.kodi.get_players.return_value = [
        {"playerid": 0, "type": "audio"},
        video,
    ]
    await coordinator.async_refresh()
    assert coordinator.data["player"] == video


async def test_reconnect_serialized(coordinator: KodiPlaybackCoordinator) -> None:
    """The media player and playback polling must not connect concurrently."""

    async def connect() -> None:
        await asyncio.sleep(0)
        coordinator.connection.connected = True

    coordinator.connection.connected = False
    coordinator.connection.connect = AsyncMock(side_effect=connect)
    await asyncio.gather(coordinator.async_connect(), coordinator.async_connect())
    coordinator.connection.connect.assert_awaited_once()


async def test_stale_track(coordinator: KodiPlaybackCoordinator) -> None:
    """Reject a selection from an old track list before sending a command."""
    await coordinator.async_refresh()
    entity = KodiTrackSelect(coordinator, "audio")
    old_option = entity.options[0]
    coordinator.kodi.get_player_properties.return_value["audiostreams"] = [{"index": 9}]
    with pytest.raises(ServiceValidationError):
        await entity.async_select_option(old_option)
    assert all(
        call.args[0] != "Player.SetAudioStream"
        for call in coordinator.kodi.call_method.await_args_list
    )


@pytest.mark.parametrize("error", [TransportError("offline"), ProtocolError("failed")])
async def test_command_failure(
    coordinator: KodiPlaybackCoordinator, error: Exception
) -> None:
    """Surface command errors without pretending the stream changed."""
    await coordinator.async_refresh()
    entity = KodiTrackSelect(coordinator, "audio")
    original = coordinator.kodi.call_method.side_effect

    async def fail_command(method: str, **kwargs: object) -> object:
        if method == "Player.SetAudioStream":
            raise error
        return await original(method, **kwargs)

    coordinator.kodi.call_method.side_effect = fail_command
    with pytest.raises(HomeAssistantError) as exc:
        await entity.async_select_option(entity.options[0])
    assert exc.value.translation_key == "track_change_failed"
    assert entity.current_option == "3: eng — Main"


async def test_duplicate_names(coordinator: KodiPlaybackCoordinator) -> None:
    """Indexes keep identical language and name combinations selectable."""
    coordinator.kodi.get_player_properties.return_value["audiostreams"].append(
        {"index": 12, "language": "eng", "name": "Main"}
    )
    await coordinator.async_refresh()
    entity = KodiTrackSelect(coordinator, "audio")
    assert entity.options == ["3: eng — Main", "12: eng — Main"]
    await entity.async_select_option(entity.options[1])
    coordinator.kodi.call_method.assert_any_await(
        "Player.SetAudioStream", playerid=1, stream=12
    )
    assert entity.current_option == entity.options[0]


async def test_platforms_without_media_player(
    hass: HomeAssistant,
    coordinator: KodiPlaybackCoordinator,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Set up, poll, control and unload entities with the media player disabled."""
    entry = MockConfigEntry(
        domain="kodi", data=TEST_IMPORT, title="Kodi", unique_id=UUID
    )
    entry.add_to_hass(hass)
    media_entry = entity_registry.async_get_or_create(
        "media_player",
        "kodi",
        UUID,
        config_entry=entry,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    with (
        patch(
            "homeassistant.components.kodi.get_kodi_connection",
            return_value=MockConnection(),
        ),
        patch("homeassistant.components.kodi.Kodi", return_value=coordinator.kodi),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert hass.states.get(media_entry.entity_id) is None
    audio_entry = entity_registry.async_get_entity_id(
        "select", "kodi", f"{UUID}_audio_track"
    )
    assert audio_entry is not None
    audio = entity_registry.async_get(audio_entry)
    assert audio is not None
    assert audio.device_id == entity_registry.async_get(media_entry.entity_id).device_id
    assert hass.states.get(audio_entry).state == "3: eng — Main"
    assert hass.states.get("sensor.name_video_width").state == "1920"
    assert hass.states.get("sensor.name_video_frame_rate").state == "23.976"
    assert hass.states.get("sensor.name_video_dynamic_range").state == "Dolby Vision"
    assert hass.states.get("sensor.name_picture_mode").state == "custom"
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": audio_entry, "option": "3: eng — Main"},
        blocking=True,
    )
    coordinator.kodi.call_method.assert_any_await(
        "Player.SetAudioStream", playerid=1, stream=3
    )
    assert hass.states.get("number.name_picture_vertical_shift").state == "0.2"
    assert hass.states.get("number.name_subtitle_vertical_margin").state == "6.0"
    assert hass.states.get("button.name_reset_picture_position").state != "unavailable"
    assert hass.states.get("button.name_reset_subtitle_margin").state != "unavailable"
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.name_picture_vertical_shift", "value": -0.4},
        blocking=True,
    )
    coordinator.kodi.call_method.assert_any_await(
        "Player.SetViewMode", viewmode={"verticalshift": -0.4}
    )
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.name_subtitle_vertical_margin", "value": 12.5},
        blocking=True,
    )
    coordinator.kodi.call_method.assert_any_await(
        "Settings.SetSettingValue", setting="subtitles.marginvertical", value=12.5
    )
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.name_reset_picture_position"},
        blocking=True,
    )
    coordinator.kodi.call_method.assert_any_await(
        "Player.SetViewMode", viewmode={"verticalshift": 0.0}
    )
    before = coordinator.kodi.get_players.await_count
    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert coordinator.kodi.get_players.await_count > before
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(audio_entry).state == "unavailable"
    before = coordinator.kodi.get_players.await_count
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert coordinator.kodi.get_players.await_count == before


@pytest.mark.parametrize(
    "stream", ["currentvideostream", "currentaudiostream", "currentsubtitle"]
)
async def test_null_stream(coordinator: KodiPlaybackCoordinator, stream: str) -> None:
    """Kodi may return null while a stream is absent or playback is ending."""
    coordinator.kodi.get_player_properties.return_value[stream] = None
    await coordinator.async_refresh()
    for description in SENSORS:
        sensor = KodiStreamSensor(coordinator, description)
        assert sensor.native_value is None or isinstance(
            sensor.native_value, (int, float, str)
        )
    assert KodiTrackSelect(coordinator, "audio").current_option in (
        None,
        "3: eng — Main",
    )
    assert KodiTrackSelect(coordinator, "subtitle").current_option in (
        None,
        "7: eng — English",
    )


async def test_connection_initializes_media_player(
    hass: HomeAssistant, coordinator: KodiPlaybackCoordinator
) -> None:
    """Polling recovery initializes callbacks and refreshes the media player."""
    connection = coordinator.connection
    connection.connected = False
    connection.can_subscribe = True
    connection.connect = AsyncMock(side_effect=CannotConnectError)
    connection.close = AsyncMock()
    kodi = coordinator.kodi
    kodi.get_application_properties = AsyncMock(
        return_value={
            "version": {"major": 21, "minor": 0},
            "volume": 100,
            "muted": False,
        }
    )
    kodi.get_playing_item_properties = AsyncMock(
        return_value={"type": "movie", "title": "Movie"}
    )
    kodi.get_player_properties.return_value.update(
        {
            "time": {"hours": 0, "minutes": 1, "seconds": 0, "milliseconds": 0},
            "totaltime": {"hours": 1, "minutes": 0, "seconds": 0, "milliseconds": 0},
            "speed": 1,
            "live": False,
        }
    )
    entry = MockConfigEntry(
        domain="kodi", data=TEST_IMPORT, title="Kodi", unique_id=UUID
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.kodi.get_kodi_connection", return_value=connection
        ),
        patch("homeassistant.components.kodi.Kodi", return_value=kodi),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert hass.states.get("media_player.name").state == "off"

    async def reconnect() -> None:
        connection.connected = True

    connection.connect.side_effect = reconnect
    await entry.runtime_data.playback.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("media_player.name").state == "playing"
    assert connection.server.Player.OnAVStart.__self__.entity_id == "media_player.name"
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    connection.close.assert_awaited_once()
