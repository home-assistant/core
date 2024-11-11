"""Tests for the Russound RIO media player."""

from unittest.mock import AsyncMock

from aiorussound.models import CallbackType
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

from . import setup_integration
from .const import ENTITY_ID_ZONE_1

from tests.common import MockConfigEntry


async def mock_state_update(client: AsyncMock) -> None:
    """Trigger a callback in the media player."""
    for callback in client.register_state_update_callbacks.call_args_list:
        await callback[0][0](client, CallbackType.STATE)


@pytest.mark.parametrize(
    ("zone_status", "source_mode", "media_player_state"),
    [
        ("ON", None, STATE_ON),
        ("ON", "playing", STATE_PLAYING),
        ("ON", "paused", STATE_PAUSED),
        ("ON", "transitioning", STATE_BUFFERING),
        ("ON", "stopped", STATE_IDLE),
        ("OFF", None, STATE_OFF),
        ("OFF", "stopped", STATE_OFF),
    ],
)
async def test_entity_state(
    hass: HomeAssistant,
    mock_russound_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    zone_status: str,
    source_mode: str | None,
    media_player_state: str,
) -> None:
    """Test media player state."""
    await setup_integration(hass, mock_config_entry)
    mock_russound_client.controllers[1].zones[1].status = zone_status
    mock_russound_client.sources[1].mode = source_mode
    await mock_state_update(mock_russound_client)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID_ZONE_1)
    assert state.state == media_player_state
