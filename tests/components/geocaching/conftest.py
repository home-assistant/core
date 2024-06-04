"""Fixtures for the Geocaching integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from geocachingapi import GeocachingStatus
import pytest

from homeassistant.components.geocaching.const import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="1234AB 1",
        domain=DOMAIN,
        data={
            "id": "mock_user",
            "auth_implementation": DOMAIN,
        },
        unique_id="mock_user",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.geocaching.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_geocaching_config_flow() -> Generator[None, MagicMock, None]:
    """Return a mocked Geocaching API client."""

    mock_status = GeocachingStatus()
    mock_status.user.username = "mock_user"

    with patch(
        "homeassistant.components.geocaching.config_flow.GeocachingApi", autospec=True
    ) as geocaching_mock:
        geocachingapi = geocaching_mock.return_value
        geocachingapi.update.return_value = mock_status
        yield geocachingapi
