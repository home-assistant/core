"""Tests for the Russound RIO media player."""

from unittest.mock import AsyncMock

from aiorussound.const import FeatureFlag
from aiorussound.exceptions import CommandError
from aiorussound.models import PlayStatus
import pytest

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MP_DOMAIN,
    SERVICE_SELECT_SOURCE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    STATE_BUFFERING,
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import mock_state_update, setup_integration
from .const import ENTITY_ID_ZONE_1

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("zone_status", "source_play_status", "media_player_state"),
    [
        (True, None, STATE_ON),
        (True, PlayStatus.PLAYING, STATE_PLAYING),
        (True, PlayStatus.PAUSED, STATE_PAUSED),
        (True, PlayStatus.TRANSITIONING, STATE_BUFFERING),
        (True, PlayStatus.STOPPED, STATE_IDLE),
        (False, None, STATE_OFF),
        (False, PlayStatus.STOPPED, STATE_OFF),
    ],
)
async def test_entity_state(
    hass: HomeAssistant,
    mock_russound_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    zone_status: bool,
    source_play_status: PlayStatus | None,
    media_player_state: str,
) -> None:
    """Test media player state."""
    await setup_integration(hass, mock_config_entry)
    mock_russound_client.controllers[1].zones[1].status = zone_status
    mock_russound_client.sources[1].play_status = source_play_status
    await mock_state_update(mock_russound_client)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID_ZONE_1)
    assert state.state == media_player_state


async def test_media_volume(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_russound_client: AsyncMock,
) -> None:
    """Test volume service."""
    await setup_integration(hass, mock_config_entry)

    # Test volume up
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_UP,
        {ATTR_ENTITY_ID: ENTITY_ID_ZONE_1},
        blocking=True,
    )

    mock_russound_client.controllers[1].zones[1].volume_up.assert_called_once()

    # Test volume down
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_DOWN,
        {ATTR_ENTITY_ID: ENTITY_ID_ZONE_1},
        blocking=True,
    )

    mock_russound_client.controllers[1].zones[1].volume_down.assert_called_once()

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: ENTITY_ID_ZONE_1, ATTR_MEDIA_VOLUME_LEVEL: 0.30},
        blocking=True,
    )

    mock_russound_client.controllers[1].zones[1].set_volume.assert_called_once_with(
        "15"
    )


async def test_volume_mute(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_russound_client: AsyncMock,
) -> None:
    """Test mute service."""
    await setup_integration(hass, mock_config_entry)

    # Test mute (w/ toggle mute support)
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID_ZONE_1, ATTR_MEDIA_VOLUME_MUTED: True},
        blocking=True,
    )

    mock_russound_client.controllers[1].zones[1].toggle_mute.assert_called_once()
    mock_russound_client.controllers[1].zones[1].toggle_mute.reset_mock()

    mock_russound_client.controllers[1].zones[1].is_mute = True

    # Test mute when already muted (w/ toggle mute support)
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID_ZONE_1, ATTR_MEDIA_VOLUME_MUTED: True},
        blocking=True,
    )

    mock_russound_client.controllers[1].zones[1].toggle_mute.assert_not_called()
    mock_russound_client.supported_features = [FeatureFlag.COMMANDS_ZONE_MUTE_OFF_ON]

    # Test mute (w/ dedicated commands)
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID_ZONE_1, ATTR_MEDIA_VOLUME_MUTED: True},
        blocking=True,
    )

    mock_russound_client.controllers[1].zones[1].mute.assert_called_once()

    # Test unmute (w/ dedicated commands)
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID_ZONE_1, ATTR_MEDIA_VOLUME_MUTED: False},
        blocking=True,
    )

    mock_russound_client.controllers[1].zones[1].unmute.assert_called_once()


@pytest.mark.parametrize(
    ("source_name", "source_id"),
    [
        ("Aux", 1),
        ("Spotify", 2),
    ],
)
async def test_source_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_russound_client: AsyncMock,
    source_name: str,
    source_id: int,
) -> None:
    """Test source service."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID_ZONE_1, ATTR_INPUT_SOURCE: source_name},
        blocking=True,
    )

    mock_russound_client.controllers[1].zones[1].select_source.assert_called_once_with(
        source_id
    )


async def test_invalid_source_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_russound_client: AsyncMock,
) -> None:
    """Test source service with invalid source ID."""
    await setup_integration(hass, mock_config_entry)

    mock_russound_client.controllers[1].zones[
        1
    ].select_source.side_effect = CommandError

    with pytest.raises(
        HomeAssistantError,
        match="Error executing async_select_source on entity media_player.mca_c5_backyard",
    ):
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: ENTITY_ID_ZONE_1, ATTR_INPUT_SOURCE: "Aux"},
            blocking=True,
        )


async def test_power_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_russound_client: AsyncMock,
) -> None:
    """Test power service."""
    await setup_integration(hass, mock_config_entry)

    data = {ATTR_ENTITY_ID: ENTITY_ID_ZONE_1}

    await hass.services.async_call(MP_DOMAIN, SERVICE_TURN_ON, data, blocking=True)

    mock_russound_client.controllers[1].zones[1].zone_on.assert_called_once()

    await hass.services.async_call(MP_DOMAIN, SERVICE_TURN_OFF, data, blocking=True)

    mock_russound_client.controllers[1].zones[1].zone_off.assert_called_once()
