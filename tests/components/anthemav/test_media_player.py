"""Test the Anthem A/V Receivers config flow."""
from collections.abc import Callable
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.media_player import (
    ATTR_APP_NAME,
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("entity_id", "entity_name"),
    [
        ("media_player.anthem_av", "Anthem AV"),
        ("media_player.anthem_av_zone_2", "Anthem AV zone 2"),
    ],
)
async def test_zones_loaded(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_id: str,
    entity_name: str,
) -> None:
    """Test zones are loaded."""

    states = hass.states.get(entity_id)

    assert states
    assert states.state == STATE_OFF
    assert states.name == entity_name


async def test_update_states_zone1(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_anthemav: AsyncMock,
    update_callback: Callable[[str], None],
) -> None:
    """Test zone states are updated."""

    mock_zone = mock_anthemav.protocol.zones[1]

    mock_zone.power = True
    mock_zone.mute = True
    mock_zone.volume_as_percentage = 42
    mock_zone.input_name = "TEST INPUT"
    mock_zone.input_format = "2.0 PCM"
    mock_anthemav.protocol.input_list = ["TEST INPUT", "INPUT 2"]

    update_callback("command")
    await hass.async_block_till_done()

    states = hass.states.get("media_player.anthem_av")
    assert states
    assert states.state == STATE_ON
    assert states.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 42
    assert states.attributes[ATTR_MEDIA_VOLUME_MUTED] is True
    assert states.attributes[ATTR_INPUT_SOURCE] == "TEST INPUT"
    assert states.attributes[ATTR_MEDIA_TITLE] == "TEST INPUT"
    assert states.attributes[ATTR_APP_NAME] == "2.0 PCM"
    assert states.attributes[ATTR_INPUT_SOURCE_LIST] == ["TEST INPUT", "INPUT 2"]
