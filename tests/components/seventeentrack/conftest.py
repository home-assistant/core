"""Configuration for 17Track tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from py17track.package import Package
import pytest

from homeassistant.components.seventeentrack.const import (
    CONF_SHOW_ARCHIVED,
    CONF_SHOW_DELIVERED,
    DEFAULT_SHOW_ARCHIVED,
    DEFAULT_SHOW_DELIVERED,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry

DEFAULT_SUMMARY = {
    "Not Found": 0,
    "In Transit": 0,
    "Expired": 0,
    "Ready to be Picked Up": 0,
    "Undelivered": 0,
    "Delivered": 0,
    "Returned": 0,
}

DEFAULT_SUMMARY_LENGTH = len(DEFAULT_SUMMARY)

ACCOUNT_ID = "1234"

NEW_SUMMARY_DATA = {
    "Not Found": 1,
    "In Transit": 1,
    "Expired": 1,
    "Ready to be Picked Up": 1,
    "Undelivered": 1,
    "Delivered": 1,
    "Returned": 1,
}

VALID_CONFIG = {
    CONF_USERNAME: "test",
    CONF_PASSWORD: "test",
}

INVALID_CONFIG = {"notusername": "seventeentrack", "notpassword": "test"}

VALID_OPTIONS = {
    CONF_SHOW_ARCHIVED: True,
    CONF_SHOW_DELIVERED: True,
}

NO_DELIVERED_OPTIONS = {
    CONF_SHOW_ARCHIVED: False,
    CONF_SHOW_DELIVERED: False,
}

VALID_PLATFORM_CONFIG_FULL = {
    "sensor": {
        "platform": "seventeentrack",
        CONF_USERNAME: "test",
        CONF_PASSWORD: "test",
        CONF_SHOW_ARCHIVED: True,
        CONF_SHOW_DELIVERED: True,
    }
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.seventeentrack.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain="seventeentrack",
        data=VALID_CONFIG,
        options=VALID_OPTIONS,
        unique_id=ACCOUNT_ID,
    )


@pytest.fixture
def mock_config_entry_with_default_options() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain="seventeentrack",
        data=VALID_CONFIG,
        options={
            CONF_SHOW_ARCHIVED: DEFAULT_SHOW_ARCHIVED,
            CONF_SHOW_DELIVERED: DEFAULT_SHOW_DELIVERED,
        },
        unique_id=ACCOUNT_ID,
    )


@pytest.fixture
def mock_seventeentrack():
    """Build a fixture for the 17Track API."""
    mock_seventeentrack_api = AsyncMock()
    with (
        patch(
            "homeassistant.components.seventeentrack.SeventeenTrackClient",
            return_value=mock_seventeentrack_api,
        ),
        patch(
            "homeassistant.components.seventeentrack.config_flow.SeventeenTrackClient",
            return_value=mock_seventeentrack_api,
        ) as mock_seventeentrack_api,
    ):
        mock_seventeentrack_api.return_value.profile.account_id = ACCOUNT_ID
        mock_seventeentrack_api.return_value.profile.login.return_value = True
        mock_seventeentrack_api.return_value.profile.packages.return_value = []
        mock_seventeentrack_api.return_value.profile.summary.return_value = (
            DEFAULT_SUMMARY
        )
        yield mock_seventeentrack_api


def get_package(
    tracking_number: str = "456",
    destination_country: int = 206,
    friendly_name: str | None = "friendly name 1",
    info_text: str = "info text 1",
    location: str = "location 1",
    timestamp: str = "2020-08-10 10:32",
    origin_country: int = 206,
    package_type: int = 2,
    status: int = 0,
    tz: str = "UTC",
):
    """Build a Package of the 17Track API."""
    return Package(
        tracking_number=tracking_number,
        destination_country=destination_country,
        friendly_name=friendly_name,
        info_text=info_text,
        location=location,
        timestamp=timestamp,
        origin_country=origin_country,
        package_type=package_type,
        status=status,
        tz=tz,
    )
