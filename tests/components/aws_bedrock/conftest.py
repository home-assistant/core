"""Test helpers for AWS Bedrock tests."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.aws_bedrock.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_CREDENTIALS = {
    "access_key_id": "test-access-key",
    "secret_access_key": "test-secret-key",
    "region": "us-east-1",
}


@pytest.fixture(autouse=True)
def mock_conversation_component(hass: HomeAssistant) -> None:
    """Mock the conversation component as loaded."""
    hass.config.components.add("conversation")


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CREDENTIALS,
        unique_id="test_unique_id",
    )


@pytest.fixture
def mock_bedrock_client() -> MagicMock:
    """Mock AWS Bedrock client."""
    mock_client = MagicMock()
    mock_client.list_foundation_models.return_value = {"modelSummaries": []}
    return mock_client
