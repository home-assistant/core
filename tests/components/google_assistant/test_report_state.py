"""Test Google report state."""
from unittest.mock import patch

from homeassistant.components.google_assistant.report_state import (
    async_enable_report_state,
)
from . import BASIC_CONFIG

from tests.common import mock_coro


async def test_report_state(hass):
    """Test report state works."""
    unsub = async_enable_report_state(hass, BASIC_CONFIG)

    with patch.object(
        BASIC_CONFIG, "async_report_state", side_effect=mock_coro
    ) as mock_report:
        hass.states.async_set("light.kitchen", "on")
        await hass.async_block_till_done()

    assert len(mock_report.mock_calls) == 1
    assert mock_report.mock_calls[0][1][0] == {
        "devices": {"states": {"light.kitchen": {"on": True, "online": True}}}
    }

    # Test that state changes that change something that Google doesn't care about
    # do not trigger a state report.
    with patch.object(
        BASIC_CONFIG, "async_report_state", side_effect=mock_coro
    ) as mock_report:
        hass.states.async_set(
            "light.kitchen", "on", {"irrelevant": "should_be_ignored"}
        )
        await hass.async_block_till_done()

    assert len(mock_report.mock_calls) == 0

    unsub()

    with patch.object(
        BASIC_CONFIG, "async_report_state", side_effect=mock_coro
    ) as mock_report:
        hass.states.async_set("light.kitchen", "on")
        await hass.async_block_till_done()

    assert len(mock_report.mock_calls) == 0
