"""Test helpers for AWS Bedrock tests."""

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.aws_bedrock.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

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
    mock_client.list_foundation_models.return_value = {
        "modelSummaries": [
            {
                "modelId": "anthropic.claude-3-sonnet-20240229-v1:0",
                "modelName": "Claude 3 Sonnet",
                "providerName": "Anthropic",
                "inferenceTypesSupported": ["ON_DEMAND"],
            },
            {
                "modelId": "meta.llama3-2-90b-instruct-v1:0",
                "modelName": "Llama 3.2 90B Instruct",
                "providerName": "Meta",
                "inferenceTypesSupported": ["ON_DEMAND"],
            },
            {
                "modelId": "amazon.nova-pro-v1:0",
                "modelName": "Nova Pro",
                "providerName": "Amazon",
                "inferenceTypesSupported": ["ON_DEMAND"],
            },
            # This model should be filtered out - doesn't support tool use
            {
                "modelId": "amazon.titan-text-premier-v1:0",
                "modelName": "Titan Text Premier",
                "providerName": "Amazon",
                "inferenceTypesSupported": ["ON_DEMAND"],
            },
        ]
    }
    return mock_client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bedrock_client: MagicMock,
) -> AsyncGenerator[MockConfigEntry]:
    """Initialize the integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("boto3.client", return_value=mock_bedrock_client),
        patch(
            "homeassistant.components.aws_bedrock.async_get_available_models",
            return_value=[
                {
                    "id": "anthropic.claude-3-sonnet-20240229-v1:0",
                    "name": "Claude 3 Sonnet",
                    "provider": "Anthropic",
                },
                {
                    "id": "meta.llama3-2-90b-instruct-v1:0",
                    "name": "Llama 3.2 90b Instruct",
                    "provider": "Meta",
                },
                {
                    "id": "amazon.nova-pro-v1:0",
                    "name": "Nova Pro",
                    "provider": "Amazon",
                },
            ],
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        yield mock_config_entry
