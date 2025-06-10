"""Fixtures for EnergyID integration tests."""

from collections.abc import AsyncGenerator, Generator
import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.energyid.const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_PROVISIONING_KEY,
    CONF_PROVISIONING_SECRET,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_PROVISIONING_KEY = "test_prov_key"
TEST_PROVISIONING_SECRET = "test_prov_secret"
TEST_DEVICE_ID = "homeassistant_eid_test1234"
TEST_DEVICE_NAME = "Home Assistant Test"
TEST_RECORD_NUMBER = "12345"
TEST_RECORD_NAME = "My Test Site"
TEST_HA_ENTITY_ID = "sensor.energy_total"
TEST_ENERGYID_KEY = "el"

MOCK_CONFIG_DATA = {
    CONF_PROVISIONING_KEY: TEST_PROVISIONING_KEY,
    CONF_PROVISIONING_SECRET: TEST_PROVISIONING_SECRET,
    CONF_DEVICE_ID: TEST_DEVICE_ID,
    CONF_DEVICE_NAME: TEST_DEVICE_NAME,
}

MOCK_OPTIONS_DATA = {
    TEST_HA_ENTITY_ID: {
        "ha_entity_id": TEST_HA_ENTITY_ID,
        "energyid_key": TEST_ENERGYID_KEY,
    }
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry with default options."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_DATA,
        options=MOCK_OPTIONS_DATA.copy(),  # Ensure tests get a fresh copy
        entry_id="test_entry_id",
        title=TEST_RECORD_NAME,
    )


@pytest.fixture
def mock_webhook_client() -> MagicMock:
    """Return a mock WebhookClient instance."""
    client = MagicMock()
    client.authenticate = AsyncMock(return_value=True)
    client.close = AsyncMock()
    client.start_auto_sync = MagicMock()
    client.update_sensor = AsyncMock()
    client.get_or_create_sensor = MagicMock()
    client.is_claimed = True
    # Use a fixed datetime for reproducible tests
    client.last_sync_time = dt.datetime(2024, 1, 1, 12, 0, 0, tzinfo=dt.UTC)
    client.webhook_url = "https://test.webhook.url/endpoint"
    client.webhook_policy = {"uploadInterval": 60, "somePolicy": True}
    client.recordNumber = TEST_RECORD_NUMBER
    client.recordName = TEST_RECORD_NAME
    client.get_claim_info = MagicMock(
        return_value={
            "claim_url": "https://example.com/claim",
            "claim_code": "ABCDEF",
            "valid_until": "2025-12-31T23:59:59Z",
        }
    )
    # Add device_name attribute expected in __init__ logging
    client.device_name = TEST_DEVICE_NAME
    return client


@pytest.fixture
def mock_webhook_client_unclaimed() -> MagicMock:
    """Return a mock WebhookClient instance that is not claimed."""
    client = MagicMock()
    client.authenticate = AsyncMock(return_value=False)
    client.close = AsyncMock()
    client.start_auto_sync = MagicMock()
    client.update_sensor = AsyncMock()
    client.get_or_create_sensor = MagicMock()
    client.is_claimed = False
    client.last_sync_time = None
    client.webhook_url = "https://test.webhook.url/endpoint"
    client.webhook_policy = {}
    client.recordNumber = None
    client.recordName = None
    client.get_claim_info = MagicMock(
        return_value={
            "claim_url": "https://example.com/claim",
            "claim_code": "ABCDEF",
            "valid_until": "2025-12-31T23:59:59Z",
        }
    )
    # Add device_name attribute expected in __init__ logging
    client.device_name = TEST_DEVICE_NAME
    return client


@pytest.fixture
def mock_setup_entry() -> AsyncGenerator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.energyid.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture(autouse=True)
def mock_energyid_webhook_client_class(
    mock_webhook_client: MagicMock,
) -> Generator[None]:
    """Mock the WebhookClient class."""
    with (
        patch(
            "homeassistant.components.energyid.WebhookClient",
            return_value=mock_webhook_client,
        ) as mock_init_client,
        patch(
            "homeassistant.components.energyid.config_flow.WebhookClient",
            return_value=mock_webhook_client,
        ) as mock_flow_client,
    ):
        # Ensure the mock instances returned by the class have the correct spec if needed elsewhere
        mock_init_client.return_value = mock_webhook_client
        mock_flow_client.return_value = mock_webhook_client
        yield


@pytest.fixture
def mock_energyid_webhook_client_class_unclaimed(
    mock_webhook_client_unclaimed: MagicMock,
) -> Generator[None]:
    """Mock the WebhookClient class to return an unclaimed client."""
    with (
        patch(
            "homeassistant.components.energyid.WebhookClient",
            return_value=mock_webhook_client_unclaimed,
        ) as mock_init_client,
        patch(
            "homeassistant.components.energyid.config_flow.WebhookClient",
            return_value=mock_webhook_client_unclaimed,
        ) as mock_flow_client,
    ):
        mock_init_client.return_value = mock_webhook_client_unclaimed
        mock_flow_client.return_value = mock_webhook_client_unclaimed
        yield


@pytest.fixture(autouse=True)
def mock_secrets_token_hex() -> Generator[None]:
    """Mock secrets.token_hex."""
    with patch(
        "homeassistant.components.energyid.config_flow.secrets.token_hex",
        return_value="fedcba98",
    ):
        yield


@pytest.fixture
async def hass_with_energyid(hass: HomeAssistant) -> HomeAssistant:
    """Return a HomeAssistant instance with the EnergyID integration loaded."""
    return hass
