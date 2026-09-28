"""Common fixtures for the Tractive tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from aiotractive import PetStatus, Trackable, TractiveStatus
from aiotractive.models import (
    tracker_status_from_rest,
    update_pet_from_health_overview,
    update_tracker_from_event,
)
from aiotractive.tracker import Tracker
import pytest

from homeassistant.components.tractive.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from tests.common import MockConfigEntry, load_json_object_fixture

TRACKER_ID = "device_id_123"
PET_ID = "pet_id_123"

HEALTH_OVERVIEW = {
    "petId": PET_ID,
    "sleep": {"minutesDaySleep": 100, "minutesNightSleep": 300, "minutesCalm": 122},
    "activity": {"minutesGoal": 200, "minutesActive": 150},
}


@pytest.fixture
def mock_tractive_client() -> Generator[AsyncMock]:
    """Mock a Tractive client."""
    trackable_object = load_json_object_fixture("trackable_object.json", DOMAIN)
    tracker_details = load_json_object_fixture("tracker_details.json", DOMAIN)
    tracker_hw_info = load_json_object_fixture("tracker_hw_info.json", DOMAIN)
    tracker_pos_report = load_json_object_fixture("tracker_pos_report.json", DOMAIN)

    status = TractiveStatus(
        trackers={
            TRACKER_ID: tracker_status_from_rest(
                tracker_details, tracker_hw_info, tracker_pos_report
            )
        },
        pets={PET_ID: PetStatus()},
    )
    update_pet_from_health_overview(status.pets[PET_ID], HEALTH_OVERVIEW)

    def notify(error: Exception | None = None) -> None:
        """Call the update listener registered by the coordinator."""
        client.subscribe_updates.call_args.args[0](error)

    def send_tracker_event(event: dict[str, Any]) -> None:
        """Apply a tracker event to the status and notify the coordinator."""
        update_tracker_from_event(status.trackers[event["tracker_id"]], event)
        notify()

    def send_hardware_event(event: dict[str, Any] | None = None) -> None:
        """Send hardware event."""
        if event is None:
            event = {
                "tracker_id": TRACKER_ID,
                "hardware": {"battery_level": 88},
                "tracker_state": "operational",
                "tracker_state_reason": "POWER_SAVING",
                "charging_state": "CHARGING",
            }
        send_tracker_event(event)

    def send_health_overview_event(event: dict[str, Any] | None = None) -> None:
        """Send health overview event."""
        if event is None:
            event = HEALTH_OVERVIEW
        update_pet_from_health_overview(
            status.pets.setdefault(event["petId"], PetStatus()), event
        )
        notify()

    def send_position_event(event: dict[str, Any] | None = None) -> None:
        """Send position event."""
        if event is None:
            event = {
                "tracker_id": TRACKER_ID,
                "position": {
                    "latlong": [22.333, 44.555],
                    "accuracy": 99,
                    "sensor_used": "GPS",
                },
            }
        send_tracker_event(event)

    def send_switch_event(event: dict[str, Any] | None = None) -> None:
        """Send switch event."""
        if event is None:
            event = {
                "tracker_id": TRACKER_ID,
                "buzzer_control": {"active": True},
                "led_control": {"active": False},
                "live_tracking": {"active": True},
            }
        send_tracker_event(event)

    def set_switch(key: str) -> AsyncMock:
        """Mock a switch command that updates the status like the library does."""

        async def _set(active: bool) -> dict[str, Any]:
            setattr(status.trackers[TRACKER_ID], key, active)
            return {"pending": True}

        return AsyncMock(side_effect=_set)

    with patch("aiotractive.Tractive", autospec=True) as mock_client:
        client = mock_client.return_value
        client.status = status
        client.async_fetch_trackables.return_value = [
            Trackable(
                pet_id=PET_ID,
                tracker_id=TRACKER_ID,
                pet_details=trackable_object,
                tracker_details=tracker_details,
            )
        ]
        client.async_fetch_status.return_value = status
        client.tracker.return_value = AsyncMock(
            spec=Tracker,
            set_live_tracking_active=set_switch("live_tracking"),
            set_buzzer_active=set_switch("buzzer"),
            set_led_active=set_switch("led"),
        )

        client.send_hardware_event = send_hardware_event
        client.send_health_overview_event = send_health_overview_event
        client.send_position_event = send_position_event
        client.send_switch_event = send_switch_event
        client.send_error_event = notify

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
