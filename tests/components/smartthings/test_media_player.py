"""Test for the SmartThings media player platform."""

from unittest.mock import AsyncMock

from pysmartthings import Attribute, Capability, Command, Status
from pysmartthings.models import HealthStatus
import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_SOUND_MODE,
    ATTR_SOUND_MODE_LIST,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    MediaPlayerEntityFeature,
    MediaPlayerService,
    MediaPlayerServiceArgument,
    RepeatMode,
)
from homeassistant.components.smartthings.const import MAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
    Platform,
    TargetKey,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    set_attribute_value,
    setup_integration,
    snapshot_smartthings_entities,
    trigger_health_update,
    trigger_update,
)


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)

    snapshot_smartthings_entities(
        hass, entity_registry, snapshot, Platform.MEDIA_PLAYER
    )


@pytest.mark.parametrize("device_fixture", ["hw_q80r_soundbar"])
@pytest.mark.parametrize(
    ("action", "command"),
    [
        (SERVICE_TURN_ON, Command.ON),
        (SERVICE_TURN_OFF, Command.OFF),
    ],
)
async def test_turn_on_off(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    action: str,
    command: Command,
) -> None:
    """Test media player turn on and off command."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        action,
        {ATTR_ENTITY_ID: "media_player.soundbar"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "afcf3b91-0000-1111-2222-ddff2a0a6577", Capability.SWITCH, command, MAIN
    )


@pytest.mark.parametrize("device_fixture", ["hw_q80r_soundbar"])
@pytest.mark.parametrize(
    ("muted", "argument"),
    [
        (True, "muted"),
        (False, "unmuted"),
    ],
)
async def test_mute_unmute(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    muted: bool,
    argument: str,
) -> None:
    """Test media player mute and unmute command."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        MediaPlayerService.VOLUME_MUTE,
        {
            TargetKey.ENTITY_ID: "media_player.soundbar",
            MediaPlayerServiceArgument.IS_VOLUME_MUTED: muted,
        },
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "afcf3b91-0000-1111-2222-ddff2a0a6577",
        Capability.AUDIO_MUTE,
        Command.SET_MUTE,
        MAIN,
        argument=argument,
    )


@pytest.mark.parametrize("device_fixture", ["hw_q80r_soundbar"])
async def test_set_volume_level(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test media player set volume level command."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        MediaPlayerService.VOLUME_SET,
        {
            TargetKey.ENTITY_ID: "media_player.soundbar",
            MediaPlayerServiceArgument.VOLUME_LEVEL: 0.31,
        },
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "afcf3b91-0000-1111-2222-ddff2a0a6577",
        Capability.AUDIO_VOLUME,
        Command.SET_VOLUME,
        MAIN,
        argument=31,
    )


@pytest.mark.parametrize("device_fixture", ["hw_q80r_soundbar"])
async def test_volume_up(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test media player increase volume level command."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        MediaPlayerService.VOLUME_UP,
        {TargetKey.ENTITY_ID: "media_player.soundbar"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "afcf3b91-0000-1111-2222-ddff2a0a6577",
        Capability.AUDIO_VOLUME,
        Command.VOLUME_UP,
        MAIN,
    )


@pytest.mark.parametrize("device_fixture", ["hw_q80r_soundbar"])
async def test_volume_down(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test media player decrease volume level command."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        MediaPlayerService.VOLUME_DOWN,
        {TargetKey.ENTITY_ID: "media_player.soundbar"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "afcf3b91-0000-1111-2222-ddff2a0a6577",
        Capability.AUDIO_VOLUME,
        Command.VOLUME_DOWN,
        MAIN,
    )


@pytest.mark.parametrize("device_fixture", ["hw_q80r_soundbar"])
async def test_media_play(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test media player play command."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        MediaPlayerService.MEDIA_PLAY,
        {TargetKey.ENTITY_ID: "media_player.soundbar"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "afcf3b91-0000-1111-2222-ddff2a0a6577",
        Capability.MEDIA_PLAYBACK,
        Command.PLAY,
        MAIN,
    )


@pytest.mark.parametrize("device_fixture", ["hw_q80r_soundbar"])
async def test_media_pause(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test media player pause command."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        MediaPlayerService.MEDIA_PAUSE,
        {TargetKey.ENTITY_ID: "media_player.soundbar"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "afcf3b91-0000-1111-2222-ddff2a0a6577",
        Capability.MEDIA_PLAYBACK,
        Command.PAUSE,
        MAIN,
    )


@pytest.mark.parametrize("device_fixture", ["hw_q80r_soundbar"])
async def test_media_stop(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test media player stop command."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        MediaPlayerService.MEDIA_STOP,
        {TargetKey.ENTITY_ID: "media_player.soundbar"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "afcf3b91-0000-1111-2222-ddff2a0a6577",
        Capability.MEDIA_PLAYBACK,
        Command.STOP,
        MAIN,
    )


@pytest.mark.parametrize("device_fixture", ["hw_q80r_soundbar"])
async def test_media_previous_track(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test media player previous track command."""
    devices.get_device_status.return_value[MAIN][Capability.MEDIA_PLAYBACK][
        Attribute.SUPPORTED_PLAYBACK_COMMANDS
    ] = Status(["rewind"])
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        MediaPlayerService.MEDIA_PREVIOUS_TRACK,
        {TargetKey.ENTITY_ID: "media_player.soundbar"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "afcf3b91-0000-1111-2222-ddff2a0a6577",
        Capability.MEDIA_PLAYBACK,
        Command.REWIND,
        MAIN,
    )


@pytest.mark.parametrize("device_fixture", ["hw_q80r_soundbar"])
async def test_media_next_track(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test media player next track command."""
    devices.get_device_status.return_value[MAIN][Capability.MEDIA_PLAYBACK][
        Attribute.SUPPORTED_PLAYBACK_COMMANDS
    ] = Status(["fastForward"])
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        MediaPlayerService.MEDIA_NEXT_TRACK,
        {TargetKey.ENTITY_ID: "media_player.soundbar"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "afcf3b91-0000-1111-2222-ddff2a0a6577",
        Capability.MEDIA_PLAYBACK,
        Command.FAST_FORWARD,
        MAIN,
    )


@pytest.mark.parametrize("device_fixture", ["hw_q80r_soundbar"])
async def test_select_source(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test media player select source command."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        MediaPlayerService.SELECT_SOURCE,
        {
            TargetKey.ENTITY_ID: "media_player.soundbar",
            MediaPlayerServiceArgument.SOURCE: "digital",
        },
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "afcf3b91-0000-1111-2222-ddff2a0a6577",
        Capability.MEDIA_INPUT_SOURCE,
        Command.SET_INPUT_SOURCE,
        MAIN,
        argument="digital",
    )


@pytest.mark.parametrize("device_fixture", ["vd_stv_2017_k"])
async def test_vd_capability_select_source(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test media player select source command using Samsung VD capability."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("media_player.theater_tv_samsung_8_series_49")
    assert state is not None
    assert MediaPlayerEntityFeature.SELECT_SOURCE in MediaPlayerEntityFeature(
        state.attributes[ATTR_SUPPORTED_FEATURES]
    )

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        MediaPlayerService.SELECT_SOURCE,
        {
            TargetKey.ENTITY_ID: "media_player.theater_tv_samsung_8_series_49",
            MediaPlayerServiceArgument.SOURCE: "hdmi1",
        },
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "4588d2d9-a8cf-40f4-9a0b-ed5dfbaccda1",
        Capability.SAMSUNG_VD_MEDIA_INPUT_SOURCE,
        Command.SET_INPUT_SOURCE,
        MAIN,
        argument="HDMI1",
    )


@pytest.mark.parametrize("device_fixture", ["vd_stv_2017_k"])
async def test_select_source_legacy_raw_id(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test select source falls back to raw ID when not found in source map.

    When a legacy/raw source ID (e.g. 'HDMI1') is passed directly instead of the
    slugified HA name ('hdmi1'), it should be forwarded as-is to SmartThings.
    """
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        MediaPlayerService.SELECT_SOURCE,
        {
            TargetKey.ENTITY_ID: "media_player.theater_tv_samsung_8_series_49",
            MediaPlayerServiceArgument.SOURCE: "HDMI1",
        },
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "4588d2d9-a8cf-40f4-9a0b-ed5dfbaccda1",
        Capability.SAMSUNG_VD_MEDIA_INPUT_SOURCE,
        Command.SET_INPUT_SOURCE,
        MAIN,
        argument="HDMI1",
    )


@pytest.mark.parametrize("device_fixture", ["vd_stv_2017_k"])
async def test_vd_capability_source_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test source state update using Samsung VD capability."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("media_player.theater_tv_samsung_8_series_49")
    assert state is not None
    assert MediaPlayerEntityFeature.SELECT_SOURCE in MediaPlayerEntityFeature(
        state.attributes[ATTR_SUPPORTED_FEATURES]
    )
    assert state.attributes[ATTR_INPUT_SOURCE] == "hdmi1"

    # Update source to dtv
    await trigger_update(
        hass,
        devices,
        "4588d2d9-a8cf-40f4-9a0b-ed5dfbaccda1",
        Capability.SAMSUNG_VD_MEDIA_INPUT_SOURCE,
        Attribute.INPUT_SOURCE,
        "dtv",
    )

    state = hass.states.get("media_player.theater_tv_samsung_8_series_49")
    assert state is not None
    assert state.attributes[ATTR_INPUT_SOURCE] == "digital_tv"


@pytest.mark.parametrize("device_fixture", ["hw_q80r_soundbar"])
@pytest.mark.parametrize(
    ("shuffle", "argument"),
    [
        (True, "enabled"),
        (False, "disabled"),
    ],
)
async def test_media_shuffle_on_off(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    shuffle: bool,
    argument: bool,
) -> None:
    """Test media player media shuffle command."""
    devices.get_device_status.return_value[MAIN][Capability.MEDIA_PLAYBACK_SHUFFLE] = {
        Attribute.PLAYBACK_SHUFFLE: Status(True)
    }
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        MediaPlayerService.SHUFFLE_SET,
        {
            TargetKey.ENTITY_ID: "media_player.soundbar",
            MediaPlayerServiceArgument.SHUFFLE: shuffle,
        },
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "afcf3b91-0000-1111-2222-ddff2a0a6577",
        Capability.MEDIA_PLAYBACK_SHUFFLE,
        Command.SET_PLAYBACK_SHUFFLE,
        MAIN,
        argument=argument,
    )


@pytest.mark.parametrize("device_fixture", ["hw_q80r_soundbar"])
@pytest.mark.parametrize(
    ("repeat", "argument"),
    [
        (RepeatMode.OFF, "off"),
        (RepeatMode.ONE, "one"),
        (RepeatMode.ALL, "all"),
    ],
)
async def test_media_repeat_mode(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    repeat: RepeatMode,
    argument: bool,
) -> None:
    """Test media player repeat mode command."""
    devices.get_device_status.return_value[MAIN][Capability.MEDIA_PLAYBACK_REPEAT] = {
        Attribute.PLAYBACK_REPEAT_MODE: Status("one")
    }
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        MediaPlayerService.REPEAT_SET,
        {
            TargetKey.ENTITY_ID: "media_player.soundbar",
            MediaPlayerServiceArgument.REPEAT: repeat,
        },
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "afcf3b91-0000-1111-2222-ddff2a0a6577",
        Capability.MEDIA_PLAYBACK_REPEAT,
        Command.SET_PLAYBACK_REPEAT_MODE,
        MAIN,
        argument=argument,
    )


@pytest.mark.parametrize("device_fixture", ["vd_network_audio_002s"])
async def test_select_sound_mode(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test media player select sound mode command."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        MediaPlayerService.SELECT_SOUND_MODE,
        {
            TargetKey.ENTITY_ID: "media_player.theater_soundbar_living",
            MediaPlayerServiceArgument.SOUND_MODE: "adaptive_sound",
        },
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "0d94e5db-8501-2355-eb4f-214163702cac",
        Capability.EXECUTE,
        Command.EXECUTE,
        MAIN,
        argument=[
            "/sec/networkaudio/soundmode",
            {"x.com.samsung.networkaudio.soundmode": "adaptive sound"},
        ],
    )
    assert (
        hass.states.get("media_player.theater_soundbar_living").attributes[
            ATTR_SOUND_MODE
        ]
        == "adaptive_sound"
    )


@pytest.mark.parametrize("device_fixture", ["vd_stv_2017_k"])
async def test_tv_sound_mode(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a TV exposes custom.soundmode as the media player sound mode."""
    set_attribute_value(
        devices,
        Capability.CUSTOM_SOUND_MODE,
        Attribute.SUPPORTED_SOUND_MODES,
        ["Standard", "Amplify", "Kino"],
    )
    set_attribute_value(
        devices, Capability.CUSTOM_SOUND_MODE, Attribute.SOUND_MODE, "Amplify"
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("media_player.theater_tv_samsung_8_series_49")
    assert state
    assert state.attributes[ATTR_SUPPORTED_FEATURES] & (
        MediaPlayerEntityFeature.SELECT_SOUND_MODE
    )
    # An unmapped name, like a localized one, passes through unchanged.
    assert state.attributes[ATTR_SOUND_MODE_LIST] == ["standard", "amplify", "Kino"]
    assert state.attributes[ATTR_SOUND_MODE] == "amplify"

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        MediaPlayerService.SELECT_SOUND_MODE,
        {
            TargetKey.ENTITY_ID: "media_player.theater_tv_samsung_8_series_49",
            MediaPlayerServiceArgument.SOUND_MODE: "standard",
        },
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "4588d2d9-a8cf-40f4-9a0b-ed5dfbaccda1",
        Capability.CUSTOM_SOUND_MODE,
        Command.SET_SOUND_MODE,
        MAIN,
        argument="Standard",
    )


@pytest.mark.parametrize("device_fixture", ["im_speaker_ai_0001"])
async def test_no_sound_mode_on_non_soundbar(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test non-soundbar network audio devices don't expose sound mode."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("media_player.galaxy_home_mini")
    assert state is not None
    assert ATTR_SOUND_MODE_LIST not in state.attributes
    assert not (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        & MediaPlayerEntityFeature.SELECT_SOUND_MODE
    )


@pytest.mark.parametrize("device_fixture", ["hw_q80r_soundbar"])
async def test_state_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("media_player.soundbar").state == STATE_PLAYING

    await trigger_update(
        hass,
        devices,
        "afcf3b91-0000-1111-2222-ddff2a0a6577",
        Capability.SWITCH,
        Attribute.SWITCH,
        "off",
    )

    assert hass.states.get("media_player.soundbar").state == STATE_OFF


@pytest.mark.parametrize("device_fixture", ["hw_q80r_soundbar"])
async def test_availability(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test availability."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("media_player.soundbar").state == STATE_PLAYING

    await trigger_health_update(
        hass, devices, "afcf3b91-0000-1111-2222-ddff2a0a6577", HealthStatus.OFFLINE
    )

    assert hass.states.get("media_player.soundbar").state == STATE_UNAVAILABLE

    await trigger_health_update(
        hass, devices, "afcf3b91-0000-1111-2222-ddff2a0a6577", HealthStatus.ONLINE
    )

    assert hass.states.get("media_player.soundbar").state == STATE_PLAYING


@pytest.mark.parametrize("device_fixture", ["hw_q80r_soundbar"])
async def test_availability_at_start(
    hass: HomeAssistant,
    unavailable_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unavailable at boot."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("media_player.soundbar").state == STATE_UNAVAILABLE
