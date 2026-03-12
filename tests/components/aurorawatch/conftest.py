"""Common fixtures for the AuroraWatch UK tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.aurorawatch.const import DOMAIN

from tests.common import MockConfigEntry

# Sample XML responses for testing
MOCK_STATUS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<current_status api_version="0.2">
    <updated>
        <datetime>2024-01-15T12:00:00Z</datetime>
    </updated>
    <site_status status_id="green" project_id="awn" site_id="lancaster" site_url="http://aurorawatch.lancs.ac.uk">
        <status_description>No significant activity</status_description>
    </site_status>
</current_status>
"""

MOCK_ACTIVITY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<activity_data api_version="0.2">
    <activity>
        <datetime>2024-01-15T11:00:00Z</datetime>
        <value>45.2</value>
    </activity>
    <activity>
        <datetime>2024-01-15T12:00:00Z</datetime>
        <value>52.7</value>
    </activity>
</activity_data>
"""

MOCK_INVALID_STATUS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<invalid_status>
    <missing_required_fields />
</invalid_status>
"""

MOCK_MALFORMED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<unclosed_tag>
"""


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.aurorawatch.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_aiohttp_session() -> Generator[AsyncMock]:
    """Mock aiohttp session."""
    with patch(
        "homeassistant.components.aurorawatch.coordinator.async_get_clientsession"
    ) as mock_session_factory:
        mock_session = AsyncMock()
        mock_session_factory.return_value = mock_session

        # Create mock responses
        mock_status_response = AsyncMock()
        mock_status_response.text = AsyncMock(return_value=MOCK_STATUS_XML)
        mock_status_response.raise_for_status = AsyncMock()

        mock_activity_response = AsyncMock()
        mock_activity_response.text = AsyncMock(return_value=MOCK_ACTIVITY_XML)
        mock_activity_response.raise_for_status = AsyncMock()

        # Mock session.get to return different responses based on URL
        async def mock_get(url):
            if "current-status.xml" in url:
                return mock_status_response
            if "sum-activity.xml" in url:
                return mock_activity_response
            return AsyncMock()

        mock_session.get = mock_get

        yield mock_session


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="AuroraWatch UK",
        data={},
        unique_id=DOMAIN,
    )
