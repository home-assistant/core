"""Fixtures for tests."""
from datetime import timedelta
import time
from unittest.mock import AsyncMock, patch

from aiowithings import Device, WithingsClient
from aiowithings.models import NotificationConfiguration
import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.withings.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_json_array_fixture
from tests.components.withings import (
    load_activity_fixture,
    load_goals_fixture,
    load_measurements_fixture,
    load_sleep_fixture,
    load_workout_fixture,
)

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
SCOPES = [
    "user.info",
    "user.metrics",
    "user.activity",
    "user.sleepevents",
]
TITLE = "henk"
USER_ID = 12345
WEBHOOK_ID = "55a7335ea8dee830eed4ef8f84cda8f6d80b83af0847dc74032e86120bffed5e"


@pytest.fixture(name="scopes")
def mock_scopes() -> list[str]:
    """Fixture to set the scopes present in the OAuth token."""
    return SCOPES


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
        DOMAIN,
    )


@pytest.fixture(name="expires_at")
def mock_expires_at() -> int:
    """Fixture to set the oauth token expiration time."""
    return time.time() + 3600


@pytest.fixture
def webhook_config_entry(expires_at: int, scopes: list[str]) -> MockConfigEntry:
    """Create Withings entry in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=TITLE,
        unique_id=str(USER_ID),
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "status": 0,
                "userid": str(USER_ID),
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": expires_at,
                "scope": ",".join(scopes),
            },
            "profile": TITLE,
            "webhook_id": WEBHOOK_ID,
        },
    )


@pytest.fixture
def cloudhook_config_entry(expires_at: int, scopes: list[str]) -> MockConfigEntry:
    """Create Withings entry in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=TITLE,
        unique_id=str(USER_ID),
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "status": 0,
                "userid": str(USER_ID),
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": expires_at,
                "scope": ",".join(scopes),
            },
            "profile": TITLE,
            "webhook_id": WEBHOOK_ID,
            "cloudhook_url": "https://hooks.nabu.casa/ABCD",
        },
    )


@pytest.fixture
def polling_config_entry(expires_at: int, scopes: list[str]) -> MockConfigEntry:
    """Create Withings entry in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=TITLE,
        unique_id=str(USER_ID),
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "status": 0,
                "userid": str(USER_ID),
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": expires_at,
                "scope": ",".join(scopes),
            },
            "profile": TITLE,
            "webhook_id": WEBHOOK_ID,
        },
    )


@pytest.fixture(name="withings")
def mock_withings():
    """Mock withings."""

    devices_json = load_json_array_fixture("withings/devices.json")
    devices = [Device.from_api(device) for device in devices_json]

    measurement_groups = load_measurements_fixture()

    notification_json = load_json_array_fixture("withings/notifications.json")
    notifications = [
        NotificationConfiguration.from_api(not_conf) for not_conf in notification_json
    ]

    workouts = load_workout_fixture()

    activities = load_activity_fixture()

    mock = AsyncMock(spec=WithingsClient)
    mock.get_devices.return_value = devices
    mock.get_goals.return_value = load_goals_fixture()
    mock.get_measurement_in_period.return_value = measurement_groups
    mock.get_measurement_since.return_value = measurement_groups
    mock.get_sleep_summary_since.return_value = load_sleep_fixture()
    mock.get_activities_since.return_value = activities
    mock.get_activities_in_period.return_value = activities
    mock.list_notification_configurations.return_value = notifications
    mock.get_workouts_since.return_value = workouts
    mock.get_workouts_in_period.return_value = workouts

    with patch(
        "homeassistant.components.withings.WithingsClient",
        return_value=mock,
    ):
        yield mock


@pytest.fixture(name="disable_webhook_delay", autouse=True)
def disable_webhook_delay():
    """Disable webhook delay."""

    mock = AsyncMock()
    with patch(
        "homeassistant.components.withings.SUBSCRIBE_DELAY",
        timedelta(seconds=0),
    ), patch(
        "homeassistant.components.withings.UNSUBSCRIBE_DELAY",
        timedelta(seconds=0),
    ):
        yield mock
