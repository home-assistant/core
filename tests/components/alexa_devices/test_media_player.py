"""Tests for the Alexa Devices media player platform."""

from copy import deepcopy
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from aioamazondevices.exceptions import (
    CannotAuthenticate,
    CannotConnect,
    CannotRetrieveData,
)
from aioamazondevices.structures import (
    AmazonMediaControls,
    AmazonMediaState,
    AmazonVolumeState,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.alexa_devices.coordinator import SCAN_INTERVAL
from homeassistant.components.media_player import (
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MP_DOMAIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_PLAY_MEDIA,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import TEST_DEVICE_1_SN

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "media_player.echo_test"


def _make_media_state(
    player_state: str = "PLAYING",
    pause_enabled: bool = True,
    next_enabled: bool = True,
    previous_enabled: bool = True,
    now_playing_title: str = "Test Title",
    now_playing_line1: str = "Test Artist",
    now_playing_line2: str = "Test Album",
    now_playing_url: str = "https://example.com/art.jpg",
    media_length: int = 300,
    media_position: int = 42,
    media_position_updated_at: datetime | None = None,
) -> AmazonMediaState:
    """Return a populated AmazonMediaState for use in tests."""
    return AmazonMediaState(
        player_state=player_state,
        pause_enabled=pause_enabled,
        next_enabled=next_enabled,
        previous_enabled=previous_enabled,
        now_playing_title=now_playing_title,
        now_playing_line1=now_playing_line1,
        now_playing_line2=now_playing_line2,
        now_playing_url=now_playing_url,
        media_length=media_length,
        media_position=media_position,
        media_position_updated_at=media_position_updated_at
        or datetime(2024, 1, 1, tzinfo=UTC),
        seek_back_enabled=False,
        seek_forward_enabled=False,
        shuffle_enabled=False,
        repeat_enabled=False,
        media_provider="Test Provider",
        media_provider_url=None,
    )


def _get_registered_event_handler(
    mock_amazon_devices_client: AsyncMock,
    event_attr: str,
) -> AsyncMock:
    """Return the callback registered on the mocked library event."""
    event = getattr(mock_amazon_devices_client, event_attr)
    event.append.assert_called_once()
    return event.append.call_args.args[0]


def _make_volume_state(volume: int = 50) -> AmazonVolumeState:
    """Return an AmazonVolumeState for use in tests."""
    return AmazonVolumeState(volume=volume, is_muted=False)


def _get_media_state_event_callback(
    mock_amazon_devices_client: AsyncMock,
) -> AsyncMock:
    """Return the registered media state event callback."""
    return _get_registered_event_handler(
        mock_amazon_devices_client, "on_media_state_event"
    )


def _get_volume_state_event_callback(
    mock_amazon_devices_client: AsyncMock,
) -> AsyncMock:
    """Return the registered volume state event callback."""
    return _get_registered_event_handler(
        mock_amazon_devices_client, "on_volume_state_event"
    )


async def _push_media_state(
    mock_amazon_devices_client: AsyncMock,
    media_state: AmazonMediaState,
) -> None:
    """Update coordinator media state via the registered event handler."""
    event_handler = _get_media_state_event_callback(mock_amazon_devices_client)
    await event_handler({TEST_DEVICE_1_SN: media_state})


async def _push_volume_state(
    mock_amazon_devices_client: AsyncMock,
    volume_state: AmazonVolumeState,
) -> None:
    """Update coordinator volume state via the registered event handler."""
    event_handler = _get_volume_state_event_callback(mock_amazon_devices_client)
    await event_handler({TEST_DEVICE_1_SN: volume_state})


async def _clear_volume_state(
    mock_amazon_devices_client: AsyncMock,
) -> None:
    """Clear coordinator volume state via the registered event handler."""
    event_handler = _get_volume_state_event_callback(mock_amazon_devices_client)
    await event_handler({})


async def _setup_media_player_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Set up integration with only the media player platform enabled."""
    with patch(
        "homeassistant.components.alexa_devices.PLATFORMS", [Platform.MEDIA_PLAYER]
    ):
        await setup_integration(hass, mock_config_entry)


@pytest.mark.usefixtures("mock_amazon_devices_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities are registered correctly (snapshot)."""
    await _setup_media_player_platform(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_media_player_not_created_for_unsupported_device(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No entity is created for a device that does not support media playback."""
    from .const import TEST_DEVICE_1  # noqa: PLC0415

    device = deepcopy(TEST_DEVICE_1)
    device.media_player_supported = False
    mock_amazon_devices_client.get_devices_data.return_value = {
        TEST_DEVICE_1_SN: device
    }

    await _setup_media_player_platform(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID) is None


@pytest.mark.parametrize(
    "side_effect",
    [
        CannotConnect,
        CannotRetrieveData,
        CannotAuthenticate,
    ],
)
async def test_coordinator_data_update_fails(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
) -> None:
    """Entity becomes unavailable when the coordinator poll raises an exception."""
    await _setup_media_player_platform(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID) is not None

    mock_amazon_devices_client.get_devices_data.side_effect = side_effect

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE


async def test_offline_device_is_unavailable(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """An offline device is reported as unavailable on initial setup."""
    mock_amazon_devices_client.get_devices_data.return_value[
        TEST_DEVICE_1_SN
    ].online = False

    await _setup_media_player_platform(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE


async def test_offline_device_recovers(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A device that comes back online leaves the unavailable state."""
    mock_amazon_devices_client.get_devices_data.return_value[
        TEST_DEVICE_1_SN
    ].online = False

    await _setup_media_player_platform(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE

    mock_amazon_devices_client.get_devices_data.return_value[
        TEST_DEVICE_1_SN
    ].online = True

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("player_state", "expected_ha_state"),
    [
        ("PLAYING", MediaPlayerState.PLAYING),
        ("PAUSED", MediaPlayerState.PAUSED),
        ("BUFFERING", MediaPlayerState.IDLE),
        ("STOPPED", MediaPlayerState.IDLE),
    ],
)
async def test_player_state(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    player_state: str,
    expected_ha_state: MediaPlayerState,
) -> None:
    """Player state is mapped correctly from the API value."""
    await _setup_media_player_platform(hass, mock_config_entry)

    await _push_media_state(
        mock_amazon_devices_client,
        media_state=_make_media_state(player_state=player_state),
    )
    await _push_volume_state(
        mock_amazon_devices_client,
        volume_state=_make_volume_state(),
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == expected_ha_state


async def test_idle_when_no_media_state(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """State is idle when the coordinator has no media state for the device."""
    await _setup_media_player_platform(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == MediaPlayerState.IDLE


@pytest.mark.parametrize(
    ("raw_volume", "expected_level"),
    [
        (0, 0.0),
        (50, 0.5),
        (100, 1.0),
    ],
)
async def test_volume_level(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    raw_volume: int,
    expected_level: float,
) -> None:
    """Volume level is converted from 0-100 integer to 0.0-1.0 float."""
    await _setup_media_player_platform(hass, mock_config_entry)

    await _push_volume_state(
        mock_amazon_devices_client,
        volume_state=_make_volume_state(raw_volume),
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes.get("volume_level") == pytest.approx(expected_level)


@pytest.mark.parametrize(
    ("raw_volume", "expected_muted"),
    [
        (0, True),
        (1, False),
        (50, False),
    ],
)
async def test_is_volume_muted(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    raw_volume: int,
    expected_muted: bool,
) -> None:
    """Volume is considered muted only when the raw level is 0."""
    await _setup_media_player_platform(hass, mock_config_entry)

    await _push_volume_state(
        mock_amazon_devices_client,
        volume_state=_make_volume_state(raw_volume),
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes.get("is_volume_muted") == expected_muted


async def test_media_metadata_attributes(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Media title, artist, album and image URL are forwarded from the API."""
    await _setup_media_player_platform(hass, mock_config_entry)

    await _push_media_state(
        mock_amazon_devices_client,
        media_state=_make_media_state(
            now_playing_title="Bohemian Rhapsody",
            now_playing_line1="Queen",
            now_playing_line2="A Night at the Opera",
            now_playing_url="https://example.com/queen.jpg",
            media_length=354,
            media_position=120,
        ),
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes.get("media_title") == "Bohemian Rhapsody"
    assert state.attributes.get("media_artist") == "Queen"
    assert state.attributes.get("media_album_name") == "A Night at the Opera"
    assert state.attributes.get("entity_picture")
    assert state.attributes["entity_picture"].startswith(
        f"/api/media_player_proxy/{ENTITY_ID}"
    )
    assert state.attributes.get("media_duration") == 354
    assert state.attributes.get("media_position") == 120


async def test_media_metadata_none_when_no_state(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Metadata attributes are absent when there is no media state."""
    await _setup_media_player_platform(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    for attr in ("media_title", "media_artist", "media_album_name", "media_duration"):
        assert state.attributes.get(attr) is None


async def test_service_set_volume_level(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """SERVICE_VOLUME_SET converts the 0.0-1.0 value and calls the API."""
    await _setup_media_player_platform(hass, mock_config_entry)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.75},
        blocking=True,
    )

    mock_amazon_devices_client.set_device_volume.assert_awaited_once()
    assert mock_amazon_devices_client.set_device_volume.call_args.args[1] == 75


async def test_service_mute_volume(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Muting sets the device volume to 0 and stores the previous level."""
    await _setup_media_player_platform(hass, mock_config_entry)

    await _push_volume_state(
        mock_amazon_devices_client,
        volume_state=_make_volume_state(60),
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: True},
        blocking=True,
    )

    mock_amazon_devices_client.set_device_volume.assert_awaited_once()
    assert mock_amazon_devices_client.set_device_volume.call_args.args[1] == 0


async def test_service_unmute_volume_restores_level(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Un-muting restores the volume level saved before muting."""
    await _setup_media_player_platform(hass, mock_config_entry)

    await _push_volume_state(
        mock_amazon_devices_client,
        volume_state=_make_volume_state(80),
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: True},
        blocking=True,
    )
    mock_amazon_devices_client.set_device_volume.reset_mock()

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: False},
        blocking=True,
    )

    mock_amazon_devices_client.set_device_volume.assert_awaited_once()
    assert mock_amazon_devices_client.set_device_volume.call_args.args[1] == 80


@pytest.mark.parametrize(
    ("service", "media_controls_attr", "media_state"),
    [
        (SERVICE_MEDIA_STOP, "Stop", _make_media_state()),
        (
            SERVICE_MEDIA_PAUSE,
            "Pause",
            _make_media_state(player_state="PLAYING", pause_enabled=True),
        ),
        (
            SERVICE_MEDIA_PLAY,
            "Play",
            _make_media_state(player_state="PAUSED", pause_enabled=True),
        ),
        (SERVICE_MEDIA_NEXT_TRACK, "Next", _make_media_state(next_enabled=True)),
        (
            SERVICE_MEDIA_PREVIOUS_TRACK,
            "Previous",
            _make_media_state(previous_enabled=True),
        ),
    ],
)
async def test_media_transport_commands(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    media_controls_attr: str,
    media_state: AmazonMediaState,
) -> None:
    """Each transport service sends the correct AmazonMediaControls command."""

    await _setup_media_player_platform(hass, mock_config_entry)

    await _push_media_state(
        mock_amazon_devices_client,
        media_state=media_state,
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        MP_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    expected_command = getattr(AmazonMediaControls, media_controls_attr)
    mock_amazon_devices_client.send_media_command.assert_awaited_once()
    assert (
        mock_amazon_devices_client.send_media_command.call_args.args[1]
        == expected_command
    )


async def test_service_play_media(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """SERVICE_PLAY_MEDIA forwards the search term and provider to the API."""
    await _setup_media_player_platform(hass, mock_config_entry)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            "media_content_id": "Abbey Road",
            "media_content_type": MediaType.MUSIC,
        },
        blocking=True,
    )

    mock_amazon_devices_client.call_alexa_music.assert_awaited_once_with(
        mock_amazon_devices_client.get_devices_data.return_value[TEST_DEVICE_1_SN],
        "Abbey Road",
        MediaType.MUSIC,
    )


@pytest.mark.parametrize(
    ("pause_enabled", "next_enabled", "previous_enabled", "expected", "absent"),
    [
        (
            True,
            True,
            True,
            [
                MediaPlayerEntityFeature.PLAY,
                MediaPlayerEntityFeature.PAUSE,
                MediaPlayerEntityFeature.NEXT_TRACK,
                MediaPlayerEntityFeature.PREVIOUS_TRACK,
            ],
            [],
        ),
        (
            False,
            True,
            False,
            [MediaPlayerEntityFeature.NEXT_TRACK],
            [
                MediaPlayerEntityFeature.PLAY,
                MediaPlayerEntityFeature.PAUSE,
                MediaPlayerEntityFeature.PREVIOUS_TRACK,
            ],
        ),
        (
            False,
            False,
            False,
            [],
            [
                MediaPlayerEntityFeature.PLAY,
                MediaPlayerEntityFeature.PAUSE,
                MediaPlayerEntityFeature.NEXT_TRACK,
                MediaPlayerEntityFeature.PREVIOUS_TRACK,
            ],
        ),
    ],
)
async def test_supported_features_are_dynamic(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    pause_enabled: bool,
    next_enabled: bool,
    previous_enabled: bool,
    expected: list[MediaPlayerEntityFeature],
    absent: list[MediaPlayerEntityFeature],
) -> None:
    """Optional feature flags appear only when the API reports them as enabled."""
    await _setup_media_player_platform(hass, mock_config_entry)

    await _push_media_state(
        mock_amazon_devices_client,
        media_state=_make_media_state(
            pause_enabled=pause_enabled,
            next_enabled=next_enabled,
            previous_enabled=previous_enabled,
        ),
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    raw = state.attributes.get("supported_features", 0)

    for feature in expected:
        assert raw & feature, f"Expected feature {feature!r} to be set"
    for feature in absent:
        assert not (raw & feature), f"Did not expect feature {feature!r} to be set"


async def test_standard_features_always_present(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """VOLUME_SET, VOLUME_STEP, VOLUME_MUTE, STOP, and PLAY_MEDIA are always supported."""
    await _setup_media_player_platform(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    raw = state.attributes.get("supported_features", 0)

    for feature in (
        MediaPlayerEntityFeature.VOLUME_SET,
        MediaPlayerEntityFeature.VOLUME_STEP,
        MediaPlayerEntityFeature.VOLUME_MUTE,
        MediaPlayerEntityFeature.STOP,
        MediaPlayerEntityFeature.PLAY_MEDIA,
    ):
        assert raw & feature, f"Expected standard feature {feature!r} to always be set"


async def test_mute_volume_no_volume_state_returns_early(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Mute returns early when there is no volume state."""
    await _setup_media_player_platform(hass, mock_config_entry)

    await _clear_volume_state(mock_amazon_devices_client)
    await hass.async_block_till_done()

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: True},
        blocking=True,
    )

    mock_amazon_devices_client.set_device_volume.assert_not_awaited()


async def test_unmute_volume_without_prev_volume_returns_early(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Unmute returns early when there is no previous volume stored."""
    await _setup_media_player_platform(hass, mock_config_entry)

    await _push_volume_state(
        mock_amazon_devices_client,
        volume_state=_make_volume_state(50),
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: False},
        blocking=True,
    )

    mock_amazon_devices_client.set_device_volume.assert_not_awaited()


async def test_unmute_volume_when_alexa_muted_restores_current_volume(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Unmute restores current volume when device was muted directly by Alexa."""
    await _setup_media_player_platform(hass, mock_config_entry)

    await _push_volume_state(
        mock_amazon_devices_client,
        volume_state=AmazonVolumeState(volume=30, is_muted=True),
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: False},
        blocking=True,
    )

    mock_amazon_devices_client.set_device_volume.assert_awaited_once()
    assert mock_amazon_devices_client.set_device_volume.call_args.args[1] == 30
