"""Common fixtures for the SolarEdge tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.solaredge.const import CONF_SITE_ID, DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry, load_json_object_fixture

SITE_ID = "1a2b3c4d5e6f7g8h"
API_KEY = "a1b2c3d4e5f6g7h8"
USERNAME = "test-username"
PASSWORD = "test-password"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.solaredge.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a MockConfigEntry with API key auth."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="SolarEdge",
        unique_id=SITE_ID,
        data={CONF_SITE_ID: SITE_ID, CONF_API_KEY: API_KEY},
    )


@pytest.fixture
def mock_config_entry_web_login() -> MockConfigEntry:
    """Return a MockConfigEntry with web login auth."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="SolarEdge",
        unique_id=SITE_ID,
        data={
            CONF_SITE_ID: SITE_ID,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )


@pytest.fixture(name="solaredge_api")
def mock_solaredge_api_fixture() -> Generator[Mock]:
    """Mock a successful SolarEdge Monitoring API."""
    api = Mock()
    api.get_details = AsyncMock(
        return_value=load_json_object_fixture("details.json", DOMAIN)
    )
    api.get_overview = AsyncMock(
        return_value=load_json_object_fixture("overview.json", DOMAIN)
    )
    api.get_inventory = AsyncMock(
        return_value=load_json_object_fixture("inventory.json", DOMAIN)
    )
    api.get_current_power_flow = AsyncMock(
        return_value=load_json_object_fixture("power_flow.json", DOMAIN)
    )
    api.get_energy_details = AsyncMock(
        return_value=load_json_object_fixture("energy_details.json", DOMAIN)
    )
    api.get_storage_data = AsyncMock(
        return_value=load_json_object_fixture("storage_data.json", DOMAIN)
    )
    with (
        patch(
            "homeassistant.components.solaredge.config_flow.aiosolaredge.SolarEdge",
            return_value=api,
        ),
        patch(
            "homeassistant.components.solaredge.SolarEdge",
            return_value=api,
        ),
    ):
        yield api


@pytest.fixture(name="solaredge_web_api")
def mock_solaredge_web_api_fixture() -> Generator[AsyncMock]:
    """Mock a successful SolarEdge Web API."""
    with (
        patch(
            "homeassistant.components.solaredge.config_flow.SolarEdgeWeb", autospec=True
        ) as mock_web_api_flow,
        patch(
            "homeassistant.components.solaredge.coordinator.SolarEdgeWeb", autospec=True
        ) as mock_web_api_coord,
    ):
        # Ensure both patches use the same mock instance
        api = mock_web_api_flow.return_value
        mock_web_api_coord.return_value = api
        api.async_get_equipment.return_value = {
            1001: {"displayName": "1.1"},
            1002: {"displayName": "1.2"},
        }
        yield api
