"""Test the Anthem A/V Receivers config flow."""
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.anthemav.const import ANTHEMAV_UDATE_SIGNAL
from homeassistant.components.media_player.const import (
    ATTR_APP_NAME,
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_VOLUME_MUTED,
)
from homeassistant.components.siren.const import ATTR_VOLUME_LEVEL
from homeassistant.const import CONF_NAME, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from tests.common import MockConfigEntry

MAIN_ENTITY_ID = "media_player.anthem_av"


@pytest.mark.parametrize(
    "entity_id",
    [
        MAIN_ENTITY_ID,
        "media_player.anthem_av_zone_2",
    ],
)
async def test_zones_loaded(
    hass: HomeAssistant, init_integration: MockConfigEntry, entity_id: str
) -> None:
    """Test load and unload AnthemAv component."""

    states = hass.states.get(entity_id)

    assert states
    assert states.state == STATE_OFF


async def test_update_states_zone1(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_anthemav: AsyncMock
) -> None:
    """Test load and unload AnthemAv component."""

    mock_zone = mock_anthemav.protocol.zones[1]

    mock_zone.power = True
    mock_zone.mute = True
    mock_zone.volume_as_percentage = 42
    mock_zone.input_name = "TEST INPUT"
    mock_zone.input_format = "2.0 PCM"
    mock_anthemav.protocol.input_list = ["TEST INPUT", "INPUT 2"]

    async_dispatcher_send(
        hass, f"{ANTHEMAV_UDATE_SIGNAL}_{init_integration.data[CONF_NAME]}"
    )
    await hass.async_block_till_done()

    states = hass.states.get(MAIN_ENTITY_ID)
    assert states
    assert states.state == STATE_ON
    assert states.attributes[ATTR_VOLUME_LEVEL] == 42
    assert states.attributes[ATTR_MEDIA_VOLUME_MUTED] is True
    assert states.attributes[ATTR_INPUT_SOURCE] == "TEST INPUT"
    assert states.attributes[ATTR_MEDIA_TITLE] == "TEST INPUT"
    assert states.attributes[ATTR_APP_NAME] == "2.0 PCM"
    assert states.attributes[ATTR_INPUT_SOURCE_LIST] == ["TEST INPUT", "INPUT 2"]
