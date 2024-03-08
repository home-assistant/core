"""Configuration for 17Track tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

DEFAULT_SUMMARY = {
    "Not Found": 0,
    "In Transit": 0,
    "Expired": 0,
    "Ready to be Picked Up": 0,
    "Undelivered": 0,
    "Delivered": 0,
    "Returned": 0,
}

ACCOUNT_ID = "1234"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.seventeentrack.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_seventeentrack():
    """Build a fixture for the 17Track API."""
    mock_seventeentrack_profile = AsyncMock(account_id=ACCOUNT_ID)
    mock_seventeentrack_api = AsyncMock(profile=mock_seventeentrack_profile)
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
        mock_seventeentrack_api.return_value.profile.login.return_value = True
        mock_seventeentrack_api.return_value.profile.packages.return_value = []
        mock_seventeentrack_api.return_value.profile.summary.return_value = (
            DEFAULT_SUMMARY
        )
        yield mock_seventeentrack_api
