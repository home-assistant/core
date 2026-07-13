"""Test the Harman Luxury media player."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aioharmanluxury import HarmanLuxuryError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    MediaPlayerEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import PLAYER_STATE

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "media_player.dining_room"


@pytest.mark.freeze_time("2024-01-01 12:00:00+00:00")
@pytest.mark.usefixtures("mock_client")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the media player entity state and attributes."""
    # Freeze the media-proxy token so the entity_picture URL is deterministic.
    with patch("secrets.token_hex", return_value="deterministic"):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_volume_set(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting the volume level."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.5},
        blocking=True,
    )
    mock_client.async_set_volume.assert_awaited_once_with(50)


async def test_volume_mute(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test muting the output."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: True},
        blocking=True,
    )
    mock_client.async_set_mute.assert_awaited_once_with(True)


@pytest.mark.parametrize(
    ("service", "command"),
    [
        (SERVICE_MEDIA_PAUSE, "pause"),
        (SERVICE_MEDIA_STOP, "stop"),
        (SERVICE_MEDIA_NEXT_TRACK, "next"),
        (SERVICE_MEDIA_PREVIOUS_TRACK, "previous"),
    ],
)
async def test_transport_commands(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    command: str,
) -> None:
    """Test transport control services forward the right command."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_client.async_control.assert_awaited_once_with(command)


async def test_command_error(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test a failing device command raises a HomeAssistantError."""
    await setup_integration(hass, mock_config_entry)
    mock_client.async_control.side_effect = HarmanLuxuryError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_PAUSE,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )


async def test_off_state(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test the player reports off when the device is not online."""
    mock_client.async_get_state.return_value = replace(PLAYER_STATE, online=False)
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state == STATE_OFF


async def test_media_play_when_paused(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test that play is available and forwarded when the source is paused."""
    mock_client.async_get_state.return_value = replace(
        PLAYER_STATE, play_state="paused"
    )
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PLAY,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_client.async_control.assert_awaited_once_with("play")


async def test_transport_features_are_independent(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test a source that only allows pause does not advertise play or stop."""
    mock_client.async_get_state.return_value = replace(
        PLAYER_STATE, can_play=False, can_pause=True, can_stop=False
    )
    await setup_integration(hass, mock_config_entry)
    features = hass.states.get(ENTITY_ID).attributes[ATTR_SUPPORTED_FEATURES]
    assert features & MediaPlayerEntityFeature.PAUSE
    assert not features & MediaPlayerEntityFeature.PLAY
    assert not features & MediaPlayerEntityFeature.STOP


async def test_becomes_unavailable_on_error(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the entity goes unavailable when polling fails."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE

    mock_client.async_get_state.side_effect = HarmanLuxuryError
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
