"""Nice G.O. event tests."""

from unittest.mock import AsyncMock, MagicMock

from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_barrier_obstructed(
    hass: HomeAssistant, mock_nice_go: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test barrier obstructed."""
    mock_nice_go.event = MagicMock()
    await setup_integration(hass, mock_config_entry, ["event"])

    await mock_nice_go.event.call_args_list[2][0][0]({"deviceId": "1"})
    await hass.async_block_till_done()

    assert hass.states.get("event.nice_go_1_barrier_obstructed") != "unknown"
