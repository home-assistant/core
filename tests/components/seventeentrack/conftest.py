"""Configuration for 17Track tests."""

from typing import Optional
from unittest.mock import AsyncMock, patch

from py17track.package import Package
import pytest

from homeassistant.components.seventeentrack.sensor import (
    CONF_SHOW_ARCHIVED,
    CONF_SHOW_DELIVERED,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

VALID_CONFIG_MINIMAL = {
    "sensor": {
        "platform": "seventeentrack",
        CONF_USERNAME: "test",
        CONF_PASSWORD: "test",
    }
}

INVALID_CONFIG = {"sensor": {"platform": "seventeentrack", "boom": "test"}}

VALID_CONFIG_FULL = {
    "sensor": {
        "platform": "seventeentrack",
        CONF_USERNAME: "test",
        CONF_PASSWORD: "test",
        CONF_SHOW_ARCHIVED: True,
        CONF_SHOW_DELIVERED: True,
    }
}

VALID_CONFIG_FULL_NO_DELIVERED = {
    "sensor": {
        "platform": "seventeentrack",
        CONF_USERNAME: "test",
        CONF_PASSWORD: "test",
        CONF_SHOW_ARCHIVED: False,
        CONF_SHOW_DELIVERED: False,
    }
}

DEFAULT_SUMMARY = {
    "Not Found": 0,
    "In Transit": 0,
    "Expired": 0,
    "Ready to be Picked Up": 0,
    "Undelivered": 0,
    "Delivered": 0,
    "Returned": 0,
}

NEW_SUMMARY_DATA = {
    "Not Found": 1,
    "In Transit": 1,
    "Expired": 1,
    "Ready to be Picked Up": 1,
    "Undelivered": 1,
    "Delivered": 1,
    "Returned": 1,
}


@pytest.fixture
def mock_seventeentrack():
    """Build a fixture for the 17Track API."""
    mock_seventeentrack_api = AsyncMock()
    with (
        patch(
            "homeassistant.components.seventeentrack.sensor.SeventeenTrackClient",
            return_value=mock_seventeentrack_api,
        ) as mock_seventeentrack_api,
    ):
        mock_seventeentrack_api.return_value.profile.login.return_value = True
        mock_seventeentrack_api.return_value.profile.packages.return_value = []
        mock_seventeentrack_api.return_value.profile.summary.return_value = (
            DEFAULT_SUMMARY
        )
        yield mock_seventeentrack_api


def get_package(
    tracking_number: str = "456",
    destination_country: int = 206,
    friendly_name: Optional[str] = "friendly name 1",
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
