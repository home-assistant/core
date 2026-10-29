"""Tests for the System Bridge media player platform."""

from collections.abc import Generator
from dataclasses import replace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion
from systembridgeconnector.const import EventType
from systembridgeconnector.exceptions import ConnectionClosedException
from systembridgeconnector.models.audio_control import AudioControl
from systembridgeconnector.models.fixtures.modules.audio import FIXTURE_AUDIO
from systembridgeconnector.models.fixtures.modules.media import FIXTURE_MEDIA
from systembridgeconnector.models.media_control import MediaAction, MediaControl
from systembridgeconnector.models.modules import Module
from systembridgeconnector.models.response import Response

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_REPEAT,
    ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK,
    SERVICE_MEDIA_STOP,
    SERVICE_REPEAT_SET,
    SERVICE_SELECT_SOURCE,
    SERVICE_SHUFFLE_SET,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    MediaPlayerEntityFeature,
    RepeatMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import FIXTURE_REQUEST_ID

ENTITY_ID = "media_player.hostname_media"
OUTPUT_ENTITY_ID = "media_player.hostname_headphones_output"
DEFAULT_OUTPUT_ENTITY_ID = "media_player.hostname_audio"
OUTPUT_ID = "alsa_output.usb-Generic_USB_Audio-00.HiFi__Speaker__sink"
HDMI_OUTPUT_ID = "alsa_output.pci-0000_00_1f.3.hdmi-stereo"


@pytest.fixture(autouse=True)
def media_player_only() -> Generator[None]:
    """Enable only the media player platform."""
    with patch(
        "homeassistant.components.system_bridge.PLATFORMS",
        [Platform.MEDIA_PLAYER],
    ):
        yield


@pytest.mark.usefixtures("init_integration")
async def test_media_player_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the media player platform."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "service_data", "expected"),
    [
        pytest.param(
            SERVICE_MEDIA_PLAY,
            {},
            MediaControl(action=MediaAction.PLAY.value),
            id="play",
        ),
        pytest.param(
            SERVICE_MEDIA_PAUSE,
            {},
            MediaControl(action=MediaAction.PAUSE.value),
            id="pause",
        ),
        pytest.param(
            SERVICE_MEDIA_STOP,
            {},
            MediaControl(action=MediaAction.STOP.value),
            id="stop",
        ),
        pytest.param(
            SERVICE_MEDIA_PREVIOUS_TRACK,
            {},
            MediaControl(action=MediaAction.PREVIOUS.value),
            id="previous",
        ),
        pytest.param(
            SERVICE_MEDIA_NEXT_TRACK,
            {},
            MediaControl(action=MediaAction.NEXT.value),
            id="next",
        ),
        pytest.param(
            SERVICE_MEDIA_SEEK,
            {ATTR_MEDIA_SEEK_POSITION: 42},
            MediaControl(action=MediaAction.SEEK.value, position=42),
            id="seek",
        ),
        pytest.param(
            SERVICE_VOLUME_SET,
            {ATTR_MEDIA_VOLUME_LEVEL: 0.3},
            MediaControl(action=MediaAction.SET_VOLUME.value, volume=0.3),
            id="volume",
        ),
        pytest.param(
            SERVICE_SHUFFLE_SET,
            {ATTR_MEDIA_SHUFFLE: False},
            MediaControl(action=MediaAction.SET_SHUFFLE.value, shuffle=False),
            id="shuffle",
        ),
        pytest.param(
            SERVICE_REPEAT_SET,
            {ATTR_MEDIA_REPEAT: RepeatMode.OFF},
            MediaControl(action=MediaAction.SET_REPEAT.value, repeat="NONE"),
            id="repeat_off",
        ),
        pytest.param(
            SERVICE_REPEAT_SET,
            {ATTR_MEDIA_REPEAT: RepeatMode.ONE},
            MediaControl(action=MediaAction.SET_REPEAT.value, repeat="TRACK"),
            id="repeat_one",
        ),
        pytest.param(
            SERVICE_REPEAT_SET,
            {ATTR_MEDIA_REPEAT: RepeatMode.ALL},
            MediaControl(action=MediaAction.SET_REPEAT.value, repeat="LIST"),
            id="repeat_all",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_media_control(
    hass: HomeAssistant,
    mock_websocket_client: MagicMock,
    service: str,
    service_data: dict[str, Any],
    expected: MediaControl,
) -> None:
    """Test media player actions send the matching media control."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
        blocking=True,
    )

    mock_websocket_client.media_control.assert_awaited_once_with(expected)


@pytest.mark.usefixtures("init_integration")
async def test_media_without_player(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test seek, volume, shuffle and repeat are not offered when not reported."""
    coordinator = mock_config_entry.runtime_data

    await coordinator.async_handle_module(
        Module.MEDIA,
        replace(FIXTURE_MEDIA, player=None, volume=None, is_seek_enabled=None),
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    features = MediaPlayerEntityFeature(state.attributes[ATTR_SUPPORTED_FEATURES])
    assert features == (
        MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.NEXT_TRACK
    )


@pytest.mark.parametrize(
    ("entity_id", "service", "service_data", "expected"),
    [
        pytest.param(
            OUTPUT_ENTITY_ID,
            SERVICE_VOLUME_SET,
            {ATTR_MEDIA_VOLUME_LEVEL: 0.3},
            AudioControl(id=OUTPUT_ID, volume=30),
            id="volume",
        ),
        pytest.param(
            OUTPUT_ENTITY_ID,
            SERVICE_VOLUME_MUTE,
            {ATTR_MEDIA_VOLUME_MUTED: True},
            AudioControl(id=OUTPUT_ID, muted=True),
            id="mute",
        ),
        pytest.param(
            DEFAULT_OUTPUT_ENTITY_ID,
            SERVICE_VOLUME_SET,
            {ATTR_MEDIA_VOLUME_LEVEL: 0.3},
            AudioControl(id=OUTPUT_ID, volume=30),
            id="default_output_volume",
        ),
        pytest.param(
            DEFAULT_OUTPUT_ENTITY_ID,
            SERVICE_SELECT_SOURCE,
            {ATTR_INPUT_SOURCE: "HDMI Output"},
            AudioControl(id=HDMI_OUTPUT_ID, default=True),
            id="default_output_source",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_audio_control(
    hass: HomeAssistant,
    mock_websocket_client: MagicMock,
    entity_id: str,
    service: str,
    service_data: dict[str, Any],
    expected: AudioControl,
) -> None:
    """Test audio device actions send the matching audio control."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id, **service_data},
        blocking=True,
    )

    mock_websocket_client.audio_control.assert_awaited_once_with(expected)


@pytest.mark.usefixtures("init_integration")
async def test_select_unknown_source(hass: HomeAssistant) -> None:
    """Test picking an output that isn't reported raises."""
    with pytest.raises(ServiceValidationError, match="No audio device named Speakers"):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: DEFAULT_OUTPUT_ENTITY_ID, ATTR_INPUT_SOURCE: "Speakers"},
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_default_output_follows_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
) -> None:
    """Test the default output player controls whichever output is the default."""
    coordinator = mock_config_entry.runtime_data
    headphones, hdmi = FIXTURE_AUDIO.outputs

    await coordinator.async_handle_module(
        Module.AUDIO,
        replace(
            FIXTURE_AUDIO,
            outputs=[replace(headphones, default=False), replace(hdmi, default=True)],
        ),
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(DEFAULT_OUTPUT_ENTITY_ID))
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is True

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: DEFAULT_OUTPUT_ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: False},
        blocking=True,
    )
    mock_websocket_client.audio_control.assert_awaited_once_with(
        AudioControl(id=hdmi.id, muted=False)
    )

    await coordinator.async_handle_module(
        Module.AUDIO, replace(FIXTURE_AUDIO, outputs=[hdmi])
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(DEFAULT_OUTPUT_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_audio_device_added_and_disconnected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a new audio device is added, and is unavailable once it's gone."""
    coordinator = mock_config_entry.runtime_data
    new_output = replace(FIXTURE_AUDIO.outputs[0], id="new_sink", name="Speakers")

    await coordinator.async_handle_module(
        Module.AUDIO,
        replace(FIXTURE_AUDIO, outputs=[*FIXTURE_AUDIO.outputs, new_output]),
    )
    await hass.async_block_till_done()

    assert hass.states.get("media_player.hostname_speakers_output")

    await coordinator.async_handle_module(
        Module.AUDIO, replace(FIXTURE_AUDIO, outputs=[])
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get("media_player.hostname_speakers_output"))
    assert state.state == STATE_UNAVAILABLE
    assert (state := hass.states.get(OUTPUT_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("entity_id", "service", "service_data", "client_method", "message"),
    [
        pytest.param(
            ENTITY_ID,
            SERVICE_MEDIA_SEEK,
            {ATTR_MEDIA_SEEK_POSITION: 42},
            "media_control",
            "Failed to control the media player: Not supported",
            id="media",
        ),
        pytest.param(
            OUTPUT_ENTITY_ID,
            SERVICE_VOLUME_SET,
            {ATTR_MEDIA_VOLUME_LEVEL: 0.3},
            "audio_control",
            "Failed to control audio device Headphones: Not supported",
            id="audio",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_control_error(
    hass: HomeAssistant,
    mock_websocket_client: MagicMock,
    entity_id: str,
    service: str,
    service_data: dict[str, Any],
    client_method: str,
    message: str,
) -> None:
    """Test an error from System Bridge raises."""
    getattr(mock_websocket_client, client_method).return_value = Response(
        id=FIXTURE_REQUEST_ID,
        type=EventType.ERROR,
        message="Not supported",
        data={},
    )

    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id, **service_data},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("entity_id", "service", "service_data", "client_method"),
    [
        pytest.param(
            ENTITY_ID,
            SERVICE_MEDIA_PLAY,
            {},
            "media_control",
            id="media",
        ),
        pytest.param(
            OUTPUT_ENTITY_ID,
            SERVICE_VOLUME_MUTE,
            {ATTR_MEDIA_VOLUME_MUTED: True},
            "audio_control",
            id="audio",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_control_connection_closed(
    hass: HomeAssistant,
    mock_websocket_client: MagicMock,
    entity_id: str,
    service: str,
    service_data: dict[str, Any],
    client_method: str,
) -> None:
    """Test a closed connection raises."""
    getattr(
        mock_websocket_client, client_method
    ).side_effect = ConnectionClosedException("Connection is closed")

    with pytest.raises(
        HomeAssistantError,
        match=r"A connection error occurred for TestSystem \(127\.0\.0\.1\)",
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id, **service_data},
            blocking=True,
        )
