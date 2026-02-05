"""Fixtures for Garmin Connect tests."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.garmin_connect.const import (
    CONF_OAUTH1_TOKEN,
    CONF_OAUTH2_TOKEN,
    DOMAIN,
)

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="test@example.com",
        data={
            CONF_OAUTH1_TOKEN: "mock_oauth1_token",
            CONF_OAUTH2_TOKEN: "mock_oauth2_token",
        },
        unique_id="test@example.com",
    )


@pytest.fixture
def mock_auth() -> Generator[MagicMock]:
    """Return a mock GarminAuth."""
    with patch(
        "homeassistant.components.garmin_connect.GarminAuth",
        autospec=True,
    ) as mock:
        auth = mock.return_value
        auth.oauth1_token = "mock_oauth1_token"
        auth.oauth2_token = "mock_oauth2_token"
        auth.is_authenticated = True
        auth.refresh_tokens = AsyncMock()
        auth.login = AsyncMock()
        auth.complete_mfa = AsyncMock()
        yield auth


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Return a mock GarminClient."""
    with patch(
        "homeassistant.components.garmin_connect.GarminClient",
        autospec=True,
    ) as mock:
        client = mock.return_value
        # fetch_core_data() returns a flat dict with all sensor data
        client.fetch_core_data = AsyncMock(
            return_value={
                "totalSteps": 10000,
                "totalDistance": 8000.0,
                "activeCalories": 500,
                "restingHeartRate": 60,
                "minHeartRate": 50,
                "maxHeartRate": 150,
                "averageStressLevel": 30,
                "bodyBatteryChargedValue": 80,
                "bodyBatteryDrainedValue": 20,
                "floorsAscended": 10,
                "dailyStepGoal": 10000,
            }
        )
        client.get_user_profile = AsyncMock(
            return_value=MagicMock(display_name="Test User")
        )
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.garmin_connect.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock


@pytest.fixture
def mock_sensor_data() -> dict:
    """Return mock sensor data for CORE coordinator."""
    return {
        "totalSteps": 10000,
        "totalDistanceMeters": 8000.0,
        "activeKilocalories": 500,
        "restingHeartRate": 60,
        "minHeartRate": 50,
        "maxHeartRate": 150,
        "averageStressLevel": 30,
        "bodyBatteryMostRecentValue": 80,
        "bodyBatteryChargedValue": 40,
        "bodyBatteryDrainedValue": 20,
        "floorsAscended": 10,
        "floorsDescended": 5,
        "dailyStepGoal": 10000,
        "sleepingMinutes": 480,
        "deepSleepMinutes": 120,
        "lightSleepMinutes": 240,
        "remSleepMinutes": 120,
        # Datetime fields - aiogarmin returns these as datetime objects
        "lastSyncTimestamp": datetime(2026, 1, 24, 12, 0, 0, tzinfo=UTC),
        "latestSpo2ReadingTime": datetime(2026, 1, 24, 5, 30, 0, tzinfo=UTC),
        "latestRespirationTime": datetime(2026, 1, 24, 11, 0, 0, tzinfo=UTC),
        "wellnessStartTime": datetime(2026, 1, 23, 23, 0, 0, tzinfo=UTC),
        "wellnessEndTime": datetime(2026, 1, 24, 16, 0, 0, tzinfo=UTC),

    }
