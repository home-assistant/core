"""Test fixtures for air-Q."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.airq.const import DOMAIN

from .common import TEST_BRIGHTNESS, TEST_DEVICE_DATA, TEST_DEVICE_INFO, TEST_USER_DATA

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry for air-Q."""
    return MockConfigEntry(
        data=TEST_USER_DATA,
        domain=DOMAIN,
        unique_id=TEST_DEVICE_INFO["id"],
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.airq.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_airq():
    """Mock the aioairq.AirQ object.

    The integration imports it in two places: in coordinator and config_flow.
    """

    with (
        patch(
            "homeassistant.components.airq.coordinator.AirQ",
            autospec=True,
        ) as mock_airq_class,
        patch(
            "homeassistant.components.airq.config_flow.AirQ",
            new=mock_airq_class,
        ),
    ):
        airq = mock_airq_class.return_value
        # Pre-configure default mock values for setup
        airq.fetch_device_info = AsyncMock(return_value=TEST_DEVICE_INFO)
        airq.get_latest_data = AsyncMock(return_value=TEST_DEVICE_DATA)
        airq.get_current_brightness = AsyncMock(return_value=TEST_BRIGHTNESS)
        yield airq
