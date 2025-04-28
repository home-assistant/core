"""Test Google report state."""

from datetime import datetime, timedelta
from http import HTTPStatus
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.google_assistant import error, report_state
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from . import BASIC_CONFIG, MockConfig

from tests.common import async_fire_time_changed


async def test_report_state(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test report state works."""
    assert await async_setup_component(hass, "switch", {})
    hass.states.async_set("light.ceiling", "off")
    hass.states.async_set("switch.ac", "on")
    hass.states.async_set(
        "event.doorbell", "unknown", attributes={"device_class": "doorbell"}
    )

    with (
        patch.object(
            BASIC_CONFIG, "async_report_state_all", AsyncMock()
        ) as mock_report,
        patch.object(report_state, "INITIAL_REPORT_DELAY", 0),
    ):
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
                "event.doorbell": {"online": True},
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
    with (
        patch(
            "homeassistant.components.google_assistant.helpers.GoogleEntity.query_serialize",
            return_value={"same": "info"},
        ),
        patch.object(
            BASIC_CONFIG, "async_report_state_all", AsyncMock()
        ) as mock_report,
    ):
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
    with (
        patch.object(
            BASIC_CONFIG, "async_report_state_all", AsyncMock()
        ) as mock_report,
        patch(
            "homeassistant.components.google_assistant.helpers.GoogleEntity.query_serialize",
            side_effect=error.SmartHomeError("mock-error", "mock-msg"),
        ),
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


@pytest.mark.freeze_time("2023-08-01 00:00:00+00:00")
async def test_report_notifications(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test report state works."""
    config = MockConfig(agent_user_ids={"1"})

    assert await async_setup_component(hass, "event", {})
    hass.states.async_set(
        "event.doorbell", "unknown", attributes={"device_class": "doorbell"}
    )

    with (
        patch.object(config, "async_report_state_all", AsyncMock()) as mock_report,
        patch.object(report_state, "INITIAL_REPORT_DELAY", 0),
    ):
        report_state.async_enable_report_state(hass, config)

        async_fire_time_changed(
            hass, datetime.fromisoformat("2023-08-01T00:01:00+00:00")
        )
        await hass.async_block_till_done()

    # Test that enabling report state does a report on event entities
    assert len(mock_report.mock_calls) == 1
    assert mock_report.mock_calls[0][1][0] == {
        "devices": {
            "states": {
                "event.doorbell": {"online": True},
            },
        }
    }

    with patch.object(
        config, "async_report_state", return_value=HTTPStatus(200)
    ) as mock_report_state:
        event_time = datetime.fromisoformat("2023-08-01T00:02:57+00:00")
        epoc_event_time = event_time.timestamp()
        hass.states.async_set(
            "event.doorbell",
            "2023-08-01T00:02:57+00:00",
            attributes={"device_class": "doorbell"},
        )
        async_fire_time_changed(
            hass, datetime.fromisoformat("2023-08-01T00:03:00+00:00")
        )
        await hass.async_block_till_done()

        assert len(mock_report_state.mock_calls) == 1
        notifications_payload = mock_report_state.mock_calls[0][1][0]["devices"][
            "notifications"
        ]["event.doorbell"]
        assert notifications_payload == {
            "ObjectDetection": {
                "objects": {"unclassified": 1},
                "priority": 0,
                "detectionTimestamp": epoc_event_time * 1000,
            }
        }
        assert "Sending event notification for entity event.doorbell" in caplog.text
        assert "Unable to send notification with result code" not in caplog.text

        hass.states.async_set(
            "event.doorbell", "unknown", attributes={"device_class": "doorbell"}
        )
        async_fire_time_changed(
            hass, datetime.fromisoformat("2023-08-01T01:01:00+00:00")
        )
        await hass.async_block_till_done()
        for call in mock_report_state.mock_calls:
            if "states" in call[1][0]["devices"]:
                states = call[1][0]["devices"]["states"]
        assert states["event.doorbell"] == {"online": True}

    # Test the notification request failed
    caplog.clear()
    with patch.object(
        config, "async_report_state", return_value=HTTPStatus(500)
    ) as mock_report_state:
        event_time = datetime.fromisoformat("2023-08-01T01:02:57+00:00")
        epoc_event_time = event_time.timestamp()
        hass.states.async_set(
            "event.doorbell",
            "2023-08-01T01:02:57+00:00",
            attributes={"device_class": "doorbell"},
        )
        async_fire_time_changed(
            hass, datetime.fromisoformat("2023-08-01T01:03:00+00:00")
        )
        await hass.async_block_till_done()
        assert len(mock_report_state.mock_calls) == 1
        for call in mock_report_state.mock_calls:
            if "notifications" in call[1][0]["devices"]:
                notifications = call[1][0]["devices"]["notifications"]
        assert notifications["event.doorbell"] == {
            "ObjectDetection": {
                "objects": {"unclassified": 1},
                "priority": 0,
                "detectionTimestamp": epoc_event_time * 1000,
            }
        }
        assert "Sending event notification for entity event.doorbell" in caplog.text
        assert (
            "Unable to send notification with result code: 500, check log for more info"
            in caplog.text
        )

    # Test disconnecting agent user
    caplog.clear()
    with (
        patch.object(
            config, "async_report_state", return_value=HTTPStatus.NOT_FOUND
        ) as mock_report_state,
        patch.object(config, "async_disconnect_agent_user"),
    ):
        event_time = datetime.fromisoformat("2023-08-01T01:03:57+00:00")
        epoc_event_time = event_time.timestamp()
        hass.states.async_set(
            "event.doorbell",
            "2023-08-01T01:03:57+00:00",
            attributes={"device_class": "doorbell"},
        )
        async_fire_time_changed(
            hass, datetime.fromisoformat("2023-08-01T01:04:00+00:00")
        )
        await hass.async_block_till_done()
        assert len(mock_report_state.mock_calls) == 2
        for call in mock_report_state.mock_calls:
            if "notifications" in call[1][0]["devices"]:
                notifications = call[1][0]["devices"]["notifications"]
            elif "states" in call[1][0]["devices"]:
                states = call[1][0]["devices"]["states"]
        assert notifications["event.doorbell"] == {
            "ObjectDetection": {
                "objects": {"unclassified": 1},
                "priority": 0,
                "detectionTimestamp": epoc_event_time * 1000,
            }
        }
        assert states["event.doorbell"] == {"online": True}
        assert "Sending event notification for entity event.doorbell" in caplog.text
        assert (
            "Unable to send notification with result code: 404, check log for more info"
            in caplog.text
        )
