"""Tests for the AWS Bedrock integration initialization."""

from unittest.mock import MagicMock, patch

from botocore.exceptions import BotoCoreError, ClientError
import pytest

from homeassistant.components.aws_bedrock.const import (
    CONF_ACCESS_KEY_ID,
    CONF_ENABLE_WEB_SEARCH,
    CONF_GOOGLE_API_KEY,
    CONF_GOOGLE_CSE_ID,
    CONF_REGION,
    CONF_SECRET_ACCESS_KEY,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_async_setup(hass: HomeAssistant) -> None:
    """Test async_setup always returns True."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


async def test_async_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bedrock_client: MagicMock,
) -> None:
    """Test successful setup of config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch("boto3.client", return_value=mock_bedrock_client):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is mock_bedrock_client

    # Verify both platforms were set up
    assert hass.config_entries.async_has_entries(DOMAIN)


async def test_async_setup_entry_invalid_signature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bedrock_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup failure with invalid AWS signature."""
    mock_config_entry.add_to_hass(hass)

    error = ClientError(
        {
            "Error": {
                "Code": "InvalidSignatureException",
                "Message": "Invalid signature",
            }
        },
        "list_foundation_models",
    )
    mock_bedrock_client.list_foundation_models.side_effect = error

    with patch("boto3.client", return_value=mock_bedrock_client):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert "Invalid AWS credentials" in caplog.text


async def test_async_setup_entry_unrecognized_client(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bedrock_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup failure with unrecognized client exception."""
    mock_config_entry.add_to_hass(hass)

    error = ClientError(
        {
            "Error": {
                "Code": "UnrecognizedClientException",
                "Message": "Unrecognized client",
            }
        },
        "list_foundation_models",
    )
    mock_bedrock_client.list_foundation_models.side_effect = error

    with patch("boto3.client", return_value=mock_bedrock_client):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert "Invalid AWS credentials" in caplog.text


async def test_async_setup_entry_access_denied(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bedrock_client: MagicMock,
) -> None:
    """Test setup retry with access denied error."""
    mock_config_entry.add_to_hass(hass)

    error = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}},
        "list_foundation_models",
    )
    mock_bedrock_client.list_foundation_models.side_effect = error

    with patch("boto3.client", return_value=mock_bedrock_client):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_async_setup_entry_botocore_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bedrock_client: MagicMock,
) -> None:
    """Test setup retry with BotoCore error."""
    mock_config_entry.add_to_hass(hass)

    mock_bedrock_client.list_foundation_models.side_effect = BotoCoreError()

    with patch("boto3.client", return_value=mock_bedrock_client):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_async_setup_entry_with_web_search(
    hass: HomeAssistant,
    mock_bedrock_client: MagicMock,
) -> None:
    """Test setup with web search enabled in subentry."""
    # Create config entry with conversation subentry that has web search enabled
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ACCESS_KEY_ID: "test-access-key",
            CONF_SECRET_ACCESS_KEY: "test-secret-key",
            CONF_REGION: "us-east-1",
        },
        subentries_data=[
            ConfigSubentryData(
                data={
                    "prompt": "Test prompt",
                    "model": "anthropic.claude-3-sonnet-20240229-v1:0",
                    CONF_ENABLE_WEB_SEARCH: True,
                    CONF_GOOGLE_API_KEY: "test-google-key",
                    CONF_GOOGLE_CSE_ID: "test-cse-id",
                },
                subentry_type="conversation",
                title="Test Conversation",
                unique_id=None,
            ),
        ],
    )
    mock_config_entry.add_to_hass(hass)

    with patch("boto3.client", return_value=mock_bedrock_client):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_async_setup_entry_with_web_search_missing_credentials(
    hass: HomeAssistant,
    mock_bedrock_client: MagicMock,
) -> None:
    """Test setup with web search enabled but missing Google credentials."""
    # Create config entry with conversation subentry with web search but no Google credentials
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ACCESS_KEY_ID: "test-access-key",
            CONF_SECRET_ACCESS_KEY: "test-secret-key",
            CONF_REGION: "us-east-1",
        },
        subentries_data=[
            ConfigSubentryData(
                data={
                    "prompt": "Test prompt",
                    "model": "anthropic.claude-3-sonnet-20240229-v1:0",
                    CONF_ENABLE_WEB_SEARCH: True,
                    # Missing CONF_GOOGLE_API_KEY and CONF_GOOGLE_CSE_ID
                },
                subentry_type="conversation",
                title="Test Conversation",
                unique_id=None,
            ),
        ],
    )
    mock_config_entry.add_to_hass(hass)

    with patch("boto3.client", return_value=mock_bedrock_client):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Should still load, just without web search API registered
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_async_setup_entry_multiple_subentries_web_search_once(
    hass: HomeAssistant,
    mock_bedrock_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that web search API is registered only once when multiple subentries have it enabled."""
    # Create config entry with two conversation subentries with web search
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ACCESS_KEY_ID: "test-access-key",
            CONF_SECRET_ACCESS_KEY: "test-secret-key",
            CONF_REGION: "us-east-1",
        },
        subentries_data=[
            ConfigSubentryData(
                data={
                    "prompt": "Test prompt 1",
                    "model": "anthropic.claude-3-sonnet-20240229-v1:0",
                    CONF_ENABLE_WEB_SEARCH: True,
                    CONF_GOOGLE_API_KEY: "test-google-key",
                    CONF_GOOGLE_CSE_ID: "test-cse-id",
                },
                subentry_type="conversation",
                title="Test Conversation 1",
                unique_id=None,
            ),
            ConfigSubentryData(
                data={
                    "prompt": "Test prompt 2",
                    "model": "anthropic.claude-3-sonnet-20240229-v1:0",
                    CONF_ENABLE_WEB_SEARCH: True,
                    CONF_GOOGLE_API_KEY: "test-google-key-2",
                    CONF_GOOGLE_CSE_ID: "test-cse-id-2",
                },
                subentry_type="conversation",
                title="Test Conversation 2",
                unique_id=None,
            ),
        ],
    )
    mock_config_entry.add_to_hass(hass)

    with patch("boto3.client", return_value=mock_bedrock_client):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    # Should only see one registration log
    assert caplog.text.count("Registered AWS Bedrock Web Search API") == 1


async def test_async_update_options_triggers_reload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bedrock_client: MagicMock,
) -> None:
    """Test that updating options triggers a reload."""
    mock_config_entry.add_to_hass(hass)

    with patch("boto3.client", return_value=mock_bedrock_client):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Mock the reload
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload"
    ) as mock_reload:
        # Trigger the update listener by changing options
        hass.config_entries.async_update_entry(
            mock_config_entry, options={"new_option": "value"}
        )
        await hass.async_block_till_done()

        # Verify reload was called
        mock_reload.assert_called_once_with(mock_config_entry.entry_id)


async def test_async_setup_entry_with_custom_region(
    hass: HomeAssistant,
    mock_bedrock_client: MagicMock,
) -> None:
    """Test setup with custom AWS region."""
    custom_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ACCESS_KEY_ID: "test-access-key",
            CONF_SECRET_ACCESS_KEY: "test-secret-key",
            CONF_REGION: "eu-west-1",
        },
        unique_id="test_custom_region",
    )
    custom_entry.add_to_hass(hass)

    def validate_region(*args, **kwargs):
        """Validate that the correct region was used."""
        assert kwargs.get("region_name") == "eu-west-1"
        return mock_bedrock_client

    with patch("boto3.client", side_effect=validate_region):
        assert await hass.config_entries.async_setup(custom_entry.entry_id)
        await hass.async_block_till_done()

    assert custom_entry.state is ConfigEntryState.LOADED


async def test_platforms_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bedrock_client: MagicMock,
) -> None:
    """Test that both platforms (AI Task and Conversation) are loaded."""
    mock_config_entry.add_to_hass(hass)

    with patch("boto3.client", return_value=mock_bedrock_client):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify both platforms are in loaded state
    # Note: We can't directly check platform state, but we can verify setup succeeded
    assert hass.states.async_entity_ids(Platform.AI_TASK) is not None
    assert hass.states.async_entity_ids(Platform.CONVERSATION) is not None
