"""Test for the SmartThings media player platform."""

from unittest.mock import AsyncMock

from pysmartthings import Attribute, Capability, Command, Status
from pysmartthings.models import HealthStatus
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_REPEAT,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_SELECT_SOURCE,
    RepeatMode,
)
from homeassistant.components.smartthings.const import MAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_REPEAT_SET,
    SERVICE_SHUFFLE_SET,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    STATE_OFF,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    setup_integration,
    snapshot_smartthings_entities,
    trigger_health_update,
    trigger_update,
)

from tests.common import MockConfigEntry


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
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: "media_player.soundbar", ATTR_MEDIA_VOLUME_MUTED: muted},
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
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: "media_player.soundbar", ATTR_MEDIA_VOLUME_LEVEL: 0.31},
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
        SERVICE_VOLUME_UP,
        {ATTR_ENTITY_ID: "media_player.soundbar"},
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
        SERVICE_VOLUME_DOWN,
        {ATTR_ENTITY_ID: "media_player.soundbar"},
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
        SERVICE_MEDIA_PLAY,
        {ATTR_ENTITY_ID: "media_player.soundbar"},
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
        SERVICE_MEDIA_PAUSE,
        {ATTR_ENTITY_ID: "media_player.soundbar"},
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
        SERVICE_MEDIA_STOP,
        {ATTR_ENTITY_ID: "media_player.soundbar"},
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
    devices.get_device_status.return_value[MAIN][Capability.MEDIA_PLAYBACK] = {
        Attribute.SUPPORTED_PLAYBACK_COMMANDS: Status(["rewind"])
    }
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PREVIOUS_TRACK,
        {ATTR_ENTITY_ID: "media_player.soundbar"},
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
    devices.get_device_status.return_value[MAIN][Capability.MEDIA_PLAYBACK] = {
        Attribute.SUPPORTED_PLAYBACK_COMMANDS: Status(["fastForward"])
    }
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_NEXT_TRACK,
        {ATTR_ENTITY_ID: "media_player.soundbar"},
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
    """Test media player stop command."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: "media_player.soundbar", ATTR_INPUT_SOURCE: "digital"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "afcf3b91-0000-1111-2222-ddff2a0a6577",
        Capability.MEDIA_INPUT_SOURCE,
        Command.SET_INPUT_SOURCE,
        MAIN,
        "digital",
    )


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
        SERVICE_SHUFFLE_SET,
        {ATTR_ENTITY_ID: "media_player.soundbar", ATTR_MEDIA_SHUFFLE: shuffle},
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
        Attribute.REPEAT_MODE: Status("one")
    }
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_REPEAT_SET,
        {ATTR_ENTITY_ID: "media_player.soundbar", ATTR_MEDIA_REPEAT: repeat},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "afcf3b91-0000-1111-2222-ddff2a0a6577",
        Capability.MEDIA_PLAYBACK_REPEAT,
        Command.SET_PLAYBACK_REPEAT_MODE,
        MAIN,
        argument=argument,
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
