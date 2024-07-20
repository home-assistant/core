"""Common fixtures for the Poolsense tests."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.poolsense.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.poolsense.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_poolsense_client() -> Generator[AsyncMock]:
    """Mock a PoolSense client."""
    with (
        patch(
            "homeassistant.components.poolsense.PoolSense",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.poolsense.config_flow.PoolSense",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.test_poolsense_credentials.return_value = True
        client.get_poolsense_data.return_value = {
            "Chlorine": 20,
            "pH": 5,
            "Water Temp": 6,
            "Battery": 80,
            "Last Seen": datetime(2021, 1, 1, 0, 0, 0, tzinfo=UTC),
            "Chlorine High": 30,
            "Chlorine Low": 20,
            "pH High": 7,
            "pH Low": 4,
            "pH Status": "red",
            "Chlorine Status": "red",
        }
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="test@test.com",
        unique_id="test@test.com",
        data={
            CONF_EMAIL: "test@test.com",
            CONF_PASSWORD: "test",
        },
    )
