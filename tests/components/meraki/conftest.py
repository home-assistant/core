"""Fixtures for the Meraki tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, load_json_array_fixture

from homeassistant.components.meraki.const import CONF_ORGANIZATION_ID, DOMAIN
from homeassistant.const import CONF_API_KEY

API_KEY = "0123456789abcdef"
ORGANIZATION_ID = "123456"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.meraki.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry for the test organization."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Home Lab",
        unique_id=ORGANIZATION_ID,
        data={CONF_API_KEY: API_KEY, CONF_ORGANIZATION_ID: ORGANIZATION_ID},
    )


@pytest.fixture
def mock_meraki_client() -> Generator[MagicMock]:
    """Mock the Meraki Dashboard API client."""
    with patch(
        "homeassistant.components.meraki.api.AsyncDashboardAPI", autospec=True
    ) as mock_client:
        client = mock_client.return_value
        client.__aenter__.return_value = client
        organizations = client.organizations = MagicMock()
        organizations.getOrganizations = AsyncMock(
            return_value=load_json_array_fixture("organizations.json", DOMAIN)
        )
        organizations.getOrganizationNetworks = AsyncMock(
            return_value=load_json_array_fixture("networks.json", DOMAIN)
        )
        networks = client.networks = MagicMock()
        networks.getNetworkClients = AsyncMock(
            return_value=load_json_array_fixture("clients.json", DOMAIN)
        )
        yield client
