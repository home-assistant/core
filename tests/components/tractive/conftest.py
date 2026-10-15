"""Common fixtures for the Tractive tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from aiotractive import PetStatus, Trackable, TrackerStatus, TractiveStatus
from aiotractive.tracker import Tracker
import pytest

from homeassistant.components.tractive.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from tests.common import MockConfigEntry, load_json_object_fixture

TRACKER_ID = "device_id_123"
PET_ID = "pet_id_123"


@pytest.fixture
def mock_tractive_client() -> Generator[AsyncMock]:
    """Mock a Tractive client."""
    trackable_object = load_json_object_fixture("trackable_object.json", DOMAIN)
    tracker_details = load_json_object_fixture("tracker_details.json", DOMAIN)

    status = TractiveStatus(
        trackers={
            TRACKER_ID: TrackerStatus(
                battery_level=96,
                tracker_state="operational",
                battery_charging=False,
                power_saving=True,
                power_saving_zone=False,
                latitude=33.222222,
                longitude=44.555555,
                accuracy=30,
                sensor_used="KNOWN_WIFI",
            )
        },
        pets={
            PET_ID: PetStatus(
                daily_goal=200,
                minutes_active=150,
                minutes_day_sleep=100,
                minutes_night_sleep=300,
                minutes_rest=122,
            )
        },
    )

    def notify(error: Exception | None = None) -> None:
        """Call the update listener registered by the coordinator."""
        client.subscribe_updates.call_args.args[0](error)

    def set_tracker_status(**fields: Any) -> None:
        """Update the tracker status and notify the coordinator."""
        for key, value in fields.items():
            setattr(status.trackers[TRACKER_ID], key, value)
        notify()

    def set_pet_status(**fields: Any) -> None:
        """Update the pet status and notify the coordinator."""
        pet = status.pets.setdefault(PET_ID, PetStatus())
        for key, value in fields.items():
            setattr(pet, key, value)
        notify()

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

        client.set_tracker_status = set_tracker_status
        client.set_pet_status = set_pet_status
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
