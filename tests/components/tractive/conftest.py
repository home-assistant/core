"""Common fixtures for the Tractive tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from aiotractive.exceptions import TractiveError
from aiotractive.trackable_object import TrackableObject
from aiotractive.tracker import Tracker
import pytest

from homeassistant.components.tractive.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

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
                "tracker_state_reason": "POWER_SAVING",
                "charging_state": "CHARGING",
            }
        coord = entry.runtime_data.coordinator
        tracker_id = event["tracker_id"]
        coord.client.status["trackers"].setdefault(tracker_id, {}).update(
            {
                "battery_level": event["hardware"]["battery_level"],
                "tracker_state": event["tracker_state"].lower(),
                "power_saving": event.get("tracker_state_reason") == "POWER_SAVING",
                "battery_charging": event["charging_state"] == "CHARGING",
            }
        )
        coord.async_set_updated_data(None)

    def send_health_overview_event(
        entry: MockConfigEntry, event: dict[str, Any] | None = None
    ):
        """Send health overview event."""
        if event is None:
            event = {
                "petId": "pet_id_123",
                "sleep": {
                    "minutesDaySleep": 100,
                    "minutesNightSleep": 300,
                    "minutesCalm": 122,
                },
                "activity": {"minutesGoal": 200, "minutesActive": 150},
            }
        coord = entry.runtime_data.coordinator
        pet_id = event["petId"]
        data = event.get("content", event)
        activity = data.get("activity") or {}
        sleep = data.get("sleep") or {}
        coord.client.status["pets"].setdefault(pet_id, {}).update(
            {
                "daily_goal": activity.get("minutesGoal"),
                "minutes_active": activity.get("minutesActive"),
                "minutes_day_sleep": sleep.get("minutesDaySleep"),
                "minutes_night_sleep": sleep.get("minutesNightSleep"),
                "minutes_rest": sleep.get("minutesCalm"),
            }
        )
        coord.async_set_updated_data(None)

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
        coord = entry.runtime_data.coordinator
        tracker_id = event["tracker_id"]
        pos = event["position"]
        latlong = pos.get("latlong", [None, None])
        coord.client.status["trackers"].setdefault(tracker_id, {}).update(
            {
                "latitude": latlong[0],
                "longitude": latlong[1],
                "accuracy": pos.get("accuracy"),
                "sensor_used": pos.get("sensor_used"),
            }
        )
        coord.async_set_updated_data(None)

    def send_switch_event(entry: MockConfigEntry, event: dict[str, Any] | None = None):
        """Send switch event."""
        if event is None:
            event = {
                "tracker_id": "device_id_123",
                "buzzer_control": {"active": True},
                "led_control": {"active": False},
                "live_tracking": {"active": True},
            }
        coord = entry.runtime_data.coordinator
        tracker_id = event["tracker_id"]
        if switch_data := event.get("buzzer_control"):
            coord.client.status["trackers"].setdefault(tracker_id, {})["buzzer"] = (
                switch_data.get("active")
            )
        if switch_data := event.get("led_control"):
            coord.client.status["trackers"].setdefault(tracker_id, {})["led"] = (
                switch_data.get("active")
            )
        if switch_data := event.get("live_tracking"):
            coord.client.status["trackers"].setdefault(tracker_id, {})[
                "live_tracking"
            ] = switch_data.get("active")
        hw_data = event.get("hardware", {})
        if "power_saving_zone_id" in hw_data:
            coord.client.status["trackers"][tracker_id]["power_saving"] = (
                hw_data.get("power_saving_zone_id") is not None
            )
        coord.async_set_updated_data(None)

    def send_server_unavailable_event(entry: MockConfigEntry) -> None:
        """Send server unavailable event."""
        coord = entry.runtime_data.coordinator
        coord.async_set_update_error(TractiveError("Connection lost"))

    trackable_object = load_json_object_fixture("trackable_object.json", DOMAIN)
    tracker_details = load_json_object_fixture("tracker_details.json", DOMAIN)
    tracker_hw_info = load_json_object_fixture("tracker_hw_info.json", DOMAIN)
    tracker_pos_report = load_json_object_fixture("tracker_pos_report.json", DOMAIN)

    with patch("aiotractive.Tractive", autospec=True) as mock_client:
        client = mock_client.return_value
        client.status = {"trackers": {}, "pets": {}}
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

        client.trackable_object.return_value = Mock(
            spec=TrackableObject,
            health_overview=AsyncMock(
                return_value={
                    "petId": "pet_id_123",
                    "sleep": {
                        "minutesDaySleep": 100,
                        "minutesNightSleep": 300,
                        "minutesCalm": 122,
                    },
                    "activity": {"minutesGoal": 200, "minutesActive": 150},
                }
            ),
        )

        client.send_hardware_event = send_hardware_event
        client.send_health_overview_event = send_health_overview_event
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
