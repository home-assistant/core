"""Test the Anthem A/V Receivers config flow."""
import pytest

from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "entity_id",
    [
        "media_player.anthem_av",
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
