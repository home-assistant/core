"""Common fixtures for the Tractive tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from aiotractive.trackable_object import TrackableObject
from aiotractive.tracker import Tracker
import pytest

from homeassistant.components.tractive.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_tractive_client() -> Generator[AsyncMock, None, None]:
    """Mock a Tractive client."""
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
        client.tracker.return_value = Mock(
            spec=Tracker,
            details=AsyncMock(return_value=tracker_details),
            hw_info=AsyncMock(return_value=tracker_hw_info),
            pos_report=AsyncMock(return_value=tracker_pos_report),
        )

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
