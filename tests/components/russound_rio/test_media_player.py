"""Tests for the Russound RIO media player."""

from unittest.mock import AsyncMock

from aiorussound.models import PlayStatus
import pytest

from homeassistant.const import (
    STATE_BUFFERING,
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import HomeAssistant

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
