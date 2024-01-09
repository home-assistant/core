"""Common fixtures for the Homeassistant Analytics tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from python_homeassistant_analytics import Analytics

from homeassistant.components.homeassistant_analytics import DOMAIN
from homeassistant.components.homeassistant_analytics.const import (
    CONF_TRACKED_INTEGRATIONS,
)

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.homeassistant_analytics.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_analytics_client() -> Generator[AsyncMock, None, None]:
    """Mock a Homeassistant Analytics client."""
    with patch(
        "homeassistant.components.homeassistant_analytics.HomeassistantAnalyticsClient.get_analytics",
        return_value=Analytics.from_json(
            load_fixture("homeassistant_analytics/data.json")
        ),
    ) as mock_client:
        yield mock_client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Homeassistant Analytics",
        data={},
        options={CONF_TRACKED_INTEGRATIONS: ["youtube", "spotify"]},
    )
