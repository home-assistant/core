"""Common fixtures for the Tractive tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from aiotractive import PetStatus, TrackerStatus, TractiveStatus
from aiotractive.exceptions import TractiveError
from aiotractive.models import (
    update_pet_from_health_overview,
    update_tracker_from_event,
)
from aiotractive.trackable_object import TrackableObject
from aiotractive.tracker import Tracker
import pytest

from homeassistant.components.tractive.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_tractive_client() -> Generator[AsyncMock]:
    """Mock a Tractive client."""

    def _tracker_status(entry: MockConfigEntry, tracker_id: str) -> TrackerStatus:
        """Return the tracker status stored on the mocked client."""
        status = entry.runtime_data.coordinator.client.status
        return status.trackers.setdefault(tracker_id, TrackerStatus())

    def _send_tracker_event(entry: MockConfigEntry, event: dict[str, Any]) -> None:
        """Apply a tracker event to the status and notify the coordinator."""
        update_tracker_from_event(_tracker_status(entry, event["tracker_id"]), event)
        entry.runtime_data.coordinator.async_set_updated_data(None)

    def send_hardware_event(
        entry: MockConfigEntry, event: dict[str, Any] | None = None
    ) -> None:
        """Send hardware event."""
        if event is None:
            event = {
                "tracker_id": "device_id_123",
                "hardware": {"battery_level": 88},
                "tracker_state": "operational",
                "tracker_state_reason": "POWER_SAVING",
                "charging_state": "CHARGING",
            }
        _send_tracker_event(entry, event)

    def send_health_overview_event(
        entry: MockConfigEntry, event: dict[str, Any] | None = None
    ) -> None:
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
        data = event.get("content", event)
        status = entry.runtime_data.coordinator.client.status
        update_pet_from_health_overview(
            status.pets.setdefault(data["petId"], PetStatus()), data
        )
        entry.runtime_data.coordinator.async_set_updated_data(None)

    def send_position_event(
        entry: MockConfigEntry, event: dict[str, Any] | None = None
    ) -> None:
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
        _send_tracker_event(entry, event)

    def send_switch_event(
        entry: MockConfigEntry, event: dict[str, Any] | None = None
    ) -> None:
        """Send switch event."""
        if event is None:
            event = {
                "tracker_id": "device_id_123",
                "buzzer_control": {"active": True},
                "led_control": {"active": False},
                "live_tracking": {"active": True},
            }
        _send_tracker_event(entry, event)

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
        client.status = TractiveStatus()
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
