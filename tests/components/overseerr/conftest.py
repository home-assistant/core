"""Overseerr tests configuration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from python_overseerr import RequestCount

from homeassistant.components.overseerr.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_URL

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.overseerr.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_overseerr_client() -> Generator[AsyncMock]:
    """Mock an Overseerr client."""
    with (
        patch(
            "homeassistant.components.overseerr.coordinator.OverseerrClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.overseerr.config_flow.OverseerrClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_request_count.return_value = RequestCount.from_json(
            load_fixture("request_count.json", DOMAIN)
        )
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Overseerr",
        data={CONF_URL: "http://overseerr.test", CONF_API_KEY: "test-key"},
    )
