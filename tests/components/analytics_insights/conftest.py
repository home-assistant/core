"""Common fixtures for the Homeassistant Analytics tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from python_homeassistant_analytics import CurrentAnalytics
from python_homeassistant_analytics.models import CustomIntegration, Integration

from homeassistant.components.analytics_insights.const import (
    CONF_TRACKED_CUSTOM_INTEGRATIONS,
    CONF_TRACKED_INTEGRATIONS,
    DOMAIN,
)

from tests.common import MockConfigEntry, load_fixture, load_json_object_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.analytics_insights.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_analytics_client() -> Generator[AsyncMock, None, None]:
    """Mock a Homeassistant Analytics client."""
    with (
        patch(
            "homeassistant.components.analytics_insights.HomeassistantAnalyticsClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.analytics_insights.config_flow.HomeassistantAnalyticsClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_current_analytics.return_value = CurrentAnalytics.from_json(
            load_fixture("analytics_insights/current_data.json")
        )
        integrations = load_json_object_fixture("analytics_insights/integrations.json")
        client.get_integrations.return_value = {
            key: Integration.from_dict(value) for key, value in integrations.items()
        }
        custom_integrations = load_json_object_fixture(
            "analytics_insights/custom_integrations.json"
        )
        client.get_custom_integrations.return_value = {
            key: CustomIntegration.from_dict(value)
            for key, value in custom_integrations.items()
        }
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Homeassistant Analytics",
        data={},
        options={
            CONF_TRACKED_INTEGRATIONS: ["youtube", "spotify", "myq"],
            CONF_TRACKED_CUSTOM_INTEGRATIONS: ["hacs"],
        },
    )
