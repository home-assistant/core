"""Fixtures for EnergyID integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.energyid.const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_PROVISIONING_KEY,
    CONF_PROVISIONING_SECRET,
    DOMAIN,
)

from tests.common import MockConfigEntry

# --- Constants for Mocking ---
TEST_PROVISIONING_KEY = "test_prov_key"
TEST_PROVISIONING_SECRET = "test_prov_secret"
TEST_INSTANCE_ID = "test_instance_123"
TEST_DEVICE_ID = f"homeassistant_eid_{TEST_INSTANCE_ID}"
TEST_DEVICE_NAME = "My Home Assistant"
TEST_RECORD_NUMBER = "site_12345"
TEST_RECORD_NAME = "My Test Site"

MOCK_CONFIG_DATA = {
    CONF_PROVISIONING_KEY: TEST_PROVISIONING_KEY,
    CONF_PROVISIONING_SECRET: TEST_PROVISIONING_SECRET,
    CONF_DEVICE_ID: TEST_DEVICE_ID,
    CONF_DEVICE_NAME: TEST_DEVICE_NAME,
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_DATA,
        entry_id="test_entry_id",
        title=TEST_RECORD_NAME,
        unique_id=TEST_RECORD_NUMBER,
    )


@pytest.fixture
def mock_webhook_client_claimed() -> MagicMock:
    """Return a mock WebhookClient instance that is already claimed."""
    client = MagicMock()
    client.authenticate = AsyncMock(return_value=True)
    client.close = AsyncMock()
    client.start_auto_sync = MagicMock()
    client.get_or_create_sensor = MagicMock(return_value=MagicMock())
    client.recordNumber = TEST_RECORD_NUMBER
    client.recordName = TEST_RECORD_NAME
    client.device_name = TEST_DEVICE_NAME
    client.webhook_policy = {"uploadInterval": 120}
    client.get_claim_info = MagicMock(
        return_value={
            "claim_url": "https://example.com/claim",
            "claim_code": "ABCDEF",
            "valid_until": "2025-12-31T23:59:59Z",
        }
    )
    return client


@pytest.fixture
def mock_webhook_client_unclaimed() -> MagicMock:
    """Return a mock WebhookClient instance that is not claimed."""
    client = MagicMock()
    client.authenticate = AsyncMock(return_value=False)
    client.close = AsyncMock()
    client.start_auto_sync = MagicMock()
    client.get_or_create_sensor = MagicMock(return_value=MagicMock())
    client.recordNumber = None
    client.recordName = None
    client.device_name = TEST_DEVICE_NAME
    client.webhook_policy = None
    client.get_claim_info = MagicMock(
        return_value={
            "claim_url": "https://example.com/claim",
            "claim_code": "ABCDEF",
            "valid_until": "2025-12-31T23:59:59Z",
        }
    )
    return client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.energyid.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture(autouse=True)
def mock_get_instance_id() -> Generator[None]:
    """Mock async_get_instance_id to return a fixed ID."""
    with patch(
        "homeassistant.helpers.instance_id.async_get",
        return_value=TEST_INSTANCE_ID,
    ):
        yield


@pytest.fixture
def mock_energyid_webhook_client_class(
    request: pytest.FixtureRequest,
    mock_webhook_client_claimed: MagicMock,
    mock_webhook_client_unclaimed: MagicMock,
) -> Generator[None]:
    """Mock the WebhookClient class.

    Uses indirect parametrization to select which mock client to use.
    Example: @pytest.mark.parametrize("mock_energyid_webhook_client_class", ["unclaimed"], indirect=True).
    """
    client_to_use = mock_webhook_client_claimed
    if hasattr(request, "param"):
        if request.param == "unclaimed":
            client_to_use = mock_webhook_client_unclaimed
        elif isinstance(request.param, Exception):
            client_to_use = MagicMock()
            client_to_use.authenticate.side_effect = request.param

    with (
        patch(
            "homeassistant.components.energyid.config_flow.WebhookClient",
            return_value=client_to_use,
        ) as mock_flow_client,
        patch(
            "homeassistant.components.energyid.WebhookClient",
            return_value=client_to_use,
        ) as mock_init_client,
    ):
        yield mock_init_client, mock_flow_client
