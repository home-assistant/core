"""Common fixtures for the Duck DNS tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.duckdns.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_DOMAIN

from tests.common import MockConfigEntry

TEST_SUBDOMAIN = "homeassistant"
TEST_TOKEN = "123e4567-e89b-12d3-a456-426614174000"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.duckdns.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Mock Duck DNS configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"{TEST_SUBDOMAIN}.duckdns.org",
        data={
            CONF_DOMAIN: TEST_SUBDOMAIN,
            CONF_ACCESS_TOKEN: TEST_TOKEN,
        },
        entry_id="12345",
    )


@pytest.fixture
def mock_update_duckdns() -> Generator[AsyncMock]:
    """Mock _update_duckdns."""

    with patch(
        "homeassistant.components.duckdns.config_flow._update_duckdns",
        return_value=True,
    ) as mock:
        yield mock
