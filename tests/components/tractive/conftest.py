"""Common fixtures for the Tractive tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from aiotractive.trackable_object import TrackableObject
from aiotractive.tracker import Tracker
import pytest

from homeassistant.components.tractive.const import DOMAIN, SERVER_UNAVAILABLE
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_tractive_client() -> Generator[AsyncMock]:
    """Mock a Tractive client."""

    def send_hardware_event(
        entry: MockConfigEntry, event: dict[str, Any] | None = None
    ):
        """Send hardware event."""
        if event is None:
            event = {
                "tracker_id": "device_id_123",
                "hardware": {"battery_level": 88},
                "tracker_state": "operational",
                "charging_state": "CHARGING",
            }
        entry.runtime_data.client._send_hardware_update(event)

    def send_wellness_event(
        entry: MockConfigEntry, event: dict[str, Any] | None = None
    ):
        """Send wellness event."""
        if event is None:
            event = {
                "pet_id": "pet_id_123",
                "sleep": {"minutes_day_sleep": 100, "minutes_night_sleep": 300},
                "wellness": {"activity_label": "ok", "sleep_label": "good"},
                "activity": {
                    "calories": 999,
                    "minutes_goal": 200,
                    "minutes_active": 150,
                    "minutes_rest": 122,
                },
            }
        entry.runtime_data.client._send_wellness_update(event)

    def send_position_event(
        entry: MockConfigEntry, event: dict[str, Any] | None = None
    ):
        """Send position event."""
        if event is None:
            event = {
                "tracker_id": "device_id_123",
                "position": {
                    "latlong": [22.333, 44.555],
                    "accuracy": 99,
                    "sensor_used": "GPS",
                },
            }
        entry.runtime_data.client._send_position_update(event)

    def send_switch_event(entry: MockConfigEntry, event: dict[str, Any] | None = None):
        """Send switch event."""
        if event is None:
            event = {
                "tracker_id": "device_id_123",
                "buzzer_control": {"active": True},
                "led_control": {"active": False},
                "live_tracking": {"active": True},
            }
        entry.runtime_data.client._send_switch_update(event)

    def send_server_unavailable_event(hass: HomeAssistant) -> None:
        """Send server unavailable event."""
        async_dispatcher_send(hass, f"{SERVER_UNAVAILABLE}-12345")

    trackable_object = load_json_object_fixture("trackable_object.json", DOMAIN)
    tracker_details = load_json_object_fixture("tracker_details.json", DOMAIN)
    tracker_hw_info = load_json_object_fixture("tracker_hw_info.json", DOMAIN)
    tracker_pos_report = load_json_object_fixture("tracker_pos_report.json", DOMAIN)

    with (
        patch(
            "homeassistant.components.tractive.aiotractive.Tractive", autospec=True
        ) as mock_client,
    ):
        client = mock_client.return_value
        client.authenticate.return_value = {"user_id": "12345"}
        client.trackable_objects.return_value = [
            Mock(
                spec=TrackableObject,
                _id="xyz123",
                type="pet",
                details=AsyncMock(return_value=trackable_object),
            ),
        ]
        client.tracker.return_value = AsyncMock(
            spec=Tracker,
            details=AsyncMock(return_value=tracker_details),
            hw_info=AsyncMock(return_value=tracker_hw_info),
            pos_report=AsyncMock(return_value=tracker_pos_report),
            set_live_tracking_active=AsyncMock(return_value={"pending": True}),
            set_buzzer_active=AsyncMock(return_value={"pending": True}),
            set_led_active=AsyncMock(return_value={"pending": True}),
        )

        client.send_hardware_event = send_hardware_event
        client.send_wellness_event = send_wellness_event
        client.send_position_event = send_position_event
        client.send_switch_event = send_switch_event
        client.send_server_unavailable_event = send_server_unavailable_event

        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: "test-email@example.com",
            CONF_PASSWORD: "test-password",
        },
        unique_id="very_unique_string",
        entry_id="3bd2acb0e4f0476d40865546d0d91921",
        title="Test Pet",
    )
