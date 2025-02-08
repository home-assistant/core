"""Nice G.O. event tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.freeze_time("2024-08-19")
async def test_barrier_obstructed(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test barrier obstructed."""
    mock_nice_go.listen = MagicMock()
    await setup_integration(hass, mock_config_entry, [Platform.EVENT])

    await mock_nice_go.listen.call_args_list[3][0][1]({"deviceId": "1"})
    await hass.async_block_till_done()

    event_state = hass.states.get("event.test_garage_1_barrier_obstructed")

    assert event_state.state == "2024-08-19T00:00:00.000+00:00"
    assert event_state.attributes["event_type"] == "barrier_obstructed"
