"""Test Google report state."""
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from homeassistant.components.google_assistant import error, report_state
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from . import BASIC_CONFIG

from tests.common import async_fire_time_changed


async def test_report_state(hass, caplog, legacy_patchable_time):
    """Test report state works."""
    assert await async_setup_component(hass, "switch", {})
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

        hass.states.async_set("light.kitchen_2", "on")
        await hass.async_block_till_done()

        assert len(mock_report.mock_calls) == 0

        async_fire_time_changed(
            hass, utcnow() + timedelta(seconds=report_state.REPORT_STATE_WINDOW)
        )
        await hass.async_block_till_done()

        assert len(mock_report.mock_calls) == 1
        assert mock_report.mock_calls[0][1][0] == {
            "devices": {
                "states": {
                    "light.kitchen": {"on": True, "online": True},
                    "light.kitchen_2": {"on": True, "online": True},
                },
            }
        }

    # Test that if serialize returns same value, we don't send
    with patch(
        "homeassistant.components.google_assistant.report_state.GoogleEntity.query_serialize",
        return_value={"same": "info"},
    ), patch.object(BASIC_CONFIG, "async_report_state_all", AsyncMock()) as mock_report:
        # New state, so reported
        hass.states.async_set("light.double_report", "on")
        await hass.async_block_till_done()

        # Changed, but serialize is same, so filtered out by extra check
        hass.states.async_set("light.double_report", "off")
        async_fire_time_changed(
            hass, utcnow() + timedelta(seconds=report_state.REPORT_STATE_WINDOW)
        )
        await hass.async_block_till_done()

        assert len(mock_report.mock_calls) == 1
        assert mock_report.mock_calls[0][1][0] == {
            "devices": {"states": {"light.double_report": {"same": "info"}}}
        }

    # Test that only significant state changes are reported
    with patch.object(
        BASIC_CONFIG, "async_report_state_all", AsyncMock()
    ) as mock_report:
        hass.states.async_set("switch.ac", "on", {"something": "else"})
        async_fire_time_changed(
            hass, utcnow() + timedelta(seconds=report_state.REPORT_STATE_WINDOW)
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
        async_fire_time_changed(
            hass, utcnow() + timedelta(seconds=report_state.REPORT_STATE_WINDOW)
        )
        await hass.async_block_till_done()

    assert "Not reporting state for light.kitchen: mock-error" in caplog.text
    assert len(mock_report.mock_calls) == 0

    unsub()

    with patch.object(
        BASIC_CONFIG, "async_report_state_all", AsyncMock()
    ) as mock_report:
        hass.states.async_set("light.kitchen", "on")
        async_fire_time_changed(
            hass, utcnow() + timedelta(seconds=report_state.REPORT_STATE_WINDOW)
        )
        await hass.async_block_till_done()

    assert len(mock_report.mock_calls) == 0
