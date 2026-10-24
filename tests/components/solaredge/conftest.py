"""Common fixtures for the SolarEdge tests."""

from collections.abc import Generator
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, load_json_object_fixture
from solaredge_web import EnergyData

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.solaredge.const import CONF_SITE_ID, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

SITE_ID = "1a2b3c4d5e6f7g8h"
TOKEN = {
    "access_token": "access-token",
    "refresh_token": "refresh-token",
    "expires_at": 4102444800,
    "expires_in": 7200,
}
USERNAME = "test-username"
PASSWORD = "test-password"
CLIENT_ID = "client-id"
CLIENT_SECRET = "client-secret"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.solaredge.async_setup_entry",
        return_value=None,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Set up SolarEdge application credentials."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a MockConfigEntry with OAuth."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="SolarEdge",
        unique_id=SITE_ID,
        data={
            CONF_SITE_ID: SITE_ID,
            "auth_implementation": DOMAIN,
            CONF_TOKEN: TOKEN,
        },
        version=2,
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
    """Mock a successful SolarEdge V2 API."""
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
            "homeassistant.components.solaredge.config_flow.SolarEdgeV2",
            return_value=api,
        ),
        patch(
            "homeassistant.components.solaredge.SolarEdgeV2",
            return_value=api,
        ),
        patch(
            "homeassistant.components.solaredge.config_entry_oauth2_flow."
            "async_get_config_entry_implementation",
            new=AsyncMock(return_value=Mock()),
        ),
        patch(
            "homeassistant.components.solaredge.config_entry_oauth2_flow.OAuth2Session"
        ) as oauth_session,
    ):
        oauth_session.return_value.token = TOKEN
        oauth_session.return_value.async_ensure_token_valid = AsyncMock()
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
            "7A012345-CA": {"name": "Optimizer 1.1", "type": "OPTIMIZER"},
            "7A012346-CA": {"name": "Optimizer 1.2", "type": "OPTIMIZER"},
        }
        api.async_get_energy_data.return_value = [
            EnergyData(
                start_time=dt_util.as_utc(datetime(2025, 1, 1, 10, 0)),
                values={"7A012345-CA": 10.0, "7A012346-CA": 20.0},
            ),
        ]
        yield api
