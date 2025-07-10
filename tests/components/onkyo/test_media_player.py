"""Test Onkyo media player platform."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

from aioonkyo import Instruction, Zone, command
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_SOUND_MODE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
)
from homeassistant.components.onkyo.services import (
    ATTR_HDMI_OUTPUT,
    SERVICE_SELECT_HDMI_OUTPUT,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "media_player.tx_nr7100"
ENTITY_ID_ZONE_2 = "media_player.tx_nr7100_zone_2"
ENTITY_ID_ZONE_3 = "media_player.tx_nr7100_zone_3"


@pytest.fixture(autouse=True)
async def auto_setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: AsyncMock,
) -> AsyncGenerator[None]:
    """Auto setup integration."""
    with (
        patch.multiple(
            "homeassistant.components.onkyo.media_player",
            AUDIO_VIDEO_INFORMATION_UPDATE_WAIT_TIME=0,
        ),
        patch("homeassistant.components.onkyo.PLATFORMS", [Platform.MEDIA_PLAYER]),
    ):
        await setup_integration(hass, mock_config_entry)
        yield


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_turn_on(hass: HomeAssistant, writes: list[Instruction]) -> None:
    """Test turn on."""
    writes.clear()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert writes[0] == command.Power(Zone.MAIN, command.Power.Param.ON)


async def test_turn_off(hass: HomeAssistant, writes: list[Instruction]) -> None:
    """Test turn off."""
    writes.clear()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert writes[0] == command.Power(Zone.MAIN, command.Power.Param.STANDBY)


async def test_volume_set(hass: HomeAssistant, writes: list[Instruction]) -> None:
    """Test volume set."""
    writes.clear()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.5},
        blocking=True,
    )
    assert writes[0] == command.Volume(Zone.MAIN, 40)


async def test_volume_up(hass: HomeAssistant, writes: list[Instruction]) -> None:
    """Test volume up."""
    writes.clear()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_UP,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert writes[0] == command.Volume(Zone.MAIN, command.Volume.Param.UP)


async def test_volume_down(hass: HomeAssistant, writes: list[Instruction]) -> None:
    """Test volume down."""
    writes.clear()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_DOWN,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert writes[0] == command.Volume(Zone.MAIN, command.Volume.Param.DOWN)


async def test_volume_mute(hass: HomeAssistant, writes: list[Instruction]) -> None:
    """Test volume mute."""
    writes.clear()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: True},
        blocking=True,
    )
    assert writes[0] == command.Muting(Zone.MAIN, command.Muting.Param.ON)

    writes.clear()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: False},
        blocking=True,
    )
    assert writes[0] == command.Muting(Zone.MAIN, command.Muting.Param.OFF)


async def test_select_source(hass: HomeAssistant, writes: list[Instruction]) -> None:
    """Test select source."""
    writes.clear()
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
    writes.clear()
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
    writes.clear()
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
    writes.clear()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_HDMI_OUTPUT,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HDMI_OUTPUT: "sub"},
        blocking=True,
    )
    assert writes[0] == command.HDMIOutput(command.HDMIOutput.Param.BOTH)
