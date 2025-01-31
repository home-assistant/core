"""Test Homee entity in general."""

from unittest.mock import MagicMock

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import build_mock_node, setup_integration

from tests.common import MockConfigEntry


async def test_connection_listener(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if loss of connection is sensed correctly."""
    mock_homee.nodes = [build_mock_node("cover_with_position_slats.json")]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("cover.test_cover")
    assert state.state != STATE_UNAVAILABLE

    mock_homee.add_connection_listener.call_args_list[1][0][0](False)
    await hass.async_block_till_done()

    state = hass.states.get("cover.test_cover")
    assert state.state == STATE_UNAVAILABLE

    mock_homee.add_connection_listener.call_args_list[1][0][0](True)
    await hass.async_block_till_done()

    state = hass.states.get("cover.test_cover")
    assert state.state != STATE_UNAVAILABLE
