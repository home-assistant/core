"""Test Google report state."""
from homeassistant.components.google_assistant import error, report_state
from homeassistant.util.dt import utcnow

from . import BASIC_CONFIG

from tests.async_mock import AsyncMock, patch
from tests.common import async_fire_time_changed


async def test_report_state(hass, caplog):
    """Test report state works."""
    hass.states.async_set("light.ceiling", "off")
    hass.states.async_set("switch.ac", "on")

    with patch.object(
        BASIC_CONFIG, "async_report_state_all", AsyncMock()
    ) as mock_report, patch.object(report_state, "INITIAL_REPORT_DELAY", 0):
        unsub = report_state.async_enable_report_state(hass, BASIC_CONFIG)

        async_fire_time_changed(hass, utcnow())
        await hass.async_block_till_done()

    # Test that enabling report state does a report on all entities
    assert len(mock_report.mock_calls) == 1
    assert mock_report.mock_calls[0][1][0] == {
        "devices": {
            "states": {
                "light.ceiling": {"on": False, "online": True},
                "switch.ac": {"on": True, "online": True},
            }
        }
    }

    with patch.object(
        BASIC_CONFIG, "async_report_state_all", AsyncMock()
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
        BASIC_CONFIG, "async_report_state_all", AsyncMock()
    ) as mock_report:
        hass.states.async_set(
            "light.kitchen", "on", {"irrelevant": "should_be_ignored"}
        )
        await hass.async_block_till_done()

    assert len(mock_report.mock_calls) == 0

    # Test that entities that we can't query don't report a state
    with patch.object(
        BASIC_CONFIG, "async_report_state_all", AsyncMock()
    ) as mock_report, patch(
        "homeassistant.components.google_assistant.report_state.GoogleEntity.query_serialize",
        side_effect=error.SmartHomeError("mock-error", "mock-msg"),
    ):
        hass.states.async_set("light.kitchen", "off")
        await hass.async_block_till_done()

    assert "Not reporting state for light.kitchen: mock-error"
    assert len(mock_report.mock_calls) == 0

    unsub()

    with patch.object(
        BASIC_CONFIG, "async_report_state_all", AsyncMock()
    ) as mock_report:
        hass.states.async_set("light.kitchen", "on")
        await hass.async_block_till_done()

    assert len(mock_report.mock_calls) == 0
