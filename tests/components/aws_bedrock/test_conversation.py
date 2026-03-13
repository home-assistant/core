"""Tests for the AWS Bedrock conversation entity."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components import conversation
from homeassistant.components.aws_bedrock.const import CONF_PROMPT, DOMAIN
from homeassistant.components.aws_bedrock.conversation import (
    AWSBedrockConversationEntity,
    async_setup_entry,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_LLM_HASS_API, MATCH_ALL
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent, llm

from tests.common import MockConfigEntry


@pytest.fixture
def mock_bedrock_client():
    """Return a mock Bedrock client."""
    client = AsyncMock()
    client.converse = AsyncMock()
    return client


@pytest.fixture
def mock_conversation_subentry_data() -> dict[str, Any]:
    """Return mock conversation subentry data."""
    return {
        CONF_PROMPT: "You are a helpful assistant.",
        CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
    }


@pytest.fixture
def mock_conversation_subentry_data_no_api() -> dict[str, Any]:
    """Return mock conversation subentry data without LLM API."""
    return {
        CONF_PROMPT: "You are a helpful assistant.",
    }


@pytest.fixture
def mock_config_entry(
    mock_conversation_subentry_data: dict[str, Any],
) -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "access_key_id": "test_key",
            "secret_access_key": "test_secret",
            "region": "us-east-1",
        },
        subentries_data=[
            ConfigSubentryData(
                data=mock_conversation_subentry_data,
                subentry_type="conversation",
                title="Test Conversation",
                unique_id=None,
            ),
        ],
    )


@pytest.fixture
def mock_config_entry_no_api(
    mock_conversation_subentry_data_no_api: dict[str, Any],
) -> MockConfigEntry:
    """Return a mock config entry without LLM API."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "access_key_id": "test_key",
            "secret_access_key": "test_secret",
            "region": "us-east-1",
        },
        subentries_data=[
            ConfigSubentryData(
                data=mock_conversation_subentry_data_no_api,
                subentry_type="conversation",
                title="Test Conversation No API",
                unique_id=None,
            ),
        ],
    )


async def test_async_setup_entry_creates_conversation_entities(
    hass: HomeAssistant,
) -> None:
    """Test that async_setup_entry creates conversation entities."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "access_key_id": "test_key",
            "secret_access_key": "test_secret",
            "region": "us-east-1",
        },
        subentries_data=[
            ConfigSubentryData(
                data={CONF_PROMPT: "Test prompt"},
                subentry_type="conversation",
                title="Test Conversation",
                unique_id=None,
            ),
        ],
    )
    config_entry.add_to_hass(hass)

    # Mock the entity platform
    entities_added = []

    def mock_add_entities(
        new_entities, update_before_add=False, *, config_subentry_id=None
    ):
        entities_added.extend(new_entities)

    with (
        patch.object(config_entry, "runtime_data", create=True) as mock_runtime_data,
        patch(
            "homeassistant.components.aws_bedrock.conversation.AWSBedrockConversationEntity.__init__",
            return_value=None,
        ),
    ):
        mock_runtime_data.client = AsyncMock()

        await async_setup_entry(hass, config_entry, mock_add_entities)

    assert len(entities_added) == 1
    assert isinstance(entities_added[0], AWSBedrockConversationEntity)


async def test_async_setup_entry_skips_non_conversation_subentries(
    hass: HomeAssistant,
) -> None:
    """Test that async_setup_entry skips non-conversation subentries."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "access_key_id": "test_key",
            "secret_access_key": "test_secret",
            "region": "us-east-1",
        },
        subentries_data=[
            ConfigSubentryData(
                data={},
                subentry_type="ai_task_data",
                title="Test AI Task",
                unique_id=None,
            ),
        ],
    )
    config_entry.add_to_hass(hass)

    entities_added = []

    def mock_add_entities(
        new_entities, update_before_add=False, *, config_subentry_id=None
    ):
        entities_added.extend(new_entities)

    with patch.object(config_entry, "runtime_data", create=True):
        await async_setup_entry(hass, config_entry, mock_add_entities)

    assert len(entities_added) == 0


def test_entity_initialization_with_llm_hass_api(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entity initialization with LLM API."""
    mock_config_entry.add_to_hass(hass)
    subentry = next(iter(mock_config_entry.subentries.values()))

    with patch.object(
        mock_config_entry, "runtime_data", create=True
    ) as mock_runtime_data:
        mock_runtime_data.client = AsyncMock()
        entity = AWSBedrockConversationEntity(mock_config_entry, subentry)

    assert entity._attr_supported_features == (
        conversation.ConversationEntityFeature.CONTROL
    )


def test_entity_initialization_without_llm_hass_api(
    hass: HomeAssistant,
    mock_config_entry_no_api: MockConfigEntry,
) -> None:
    """Test entity initialization without LLM API."""
    mock_config_entry_no_api.add_to_hass(hass)
    subentry = next(iter(mock_config_entry_no_api.subentries.values()))

    with patch.object(
        mock_config_entry_no_api, "runtime_data", create=True
    ) as mock_runtime_data:
        mock_runtime_data.client = AsyncMock()
        entity = AWSBedrockConversationEntity(mock_config_entry_no_api, subentry)

    # Should not have CONTROL feature set - defaults to parent class value
    # (ConversationEntity doesn't set _attr_supported_features by default)
    # We just need to make sure it's not explicitly set to CONTROL
    assert getattr(entity, "_attr_supported_features", None) != (
        conversation.ConversationEntityFeature.CONTROL
    )


def test_supported_languages_returns_match_all(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that supported_languages returns MATCH_ALL."""
    mock_config_entry.add_to_hass(hass)
    subentry = next(iter(mock_config_entry.subentries.values()))

    with patch.object(
        mock_config_entry, "runtime_data", create=True
    ) as mock_runtime_data:
        mock_runtime_data.client = AsyncMock()
        entity = AWSBedrockConversationEntity(mock_config_entry, subentry)

    assert entity.supported_languages == MATCH_ALL


async def test_async_handle_message_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful message handling."""
    mock_config_entry.add_to_hass(hass)
    subentry = next(iter(mock_config_entry.subentries.values()))

    with patch.object(
        mock_config_entry, "runtime_data", create=True
    ) as mock_runtime_data:
        mock_runtime_data.client = AsyncMock()
        entity = AWSBedrockConversationEntity(mock_config_entry, subentry)
        entity.hass = hass
        entity.entity_id = "conversation.aws_bedrock_test"

    user_input = conversation.ConversationInput(
        text="Turn on the lights",
        context=Context(),
        conversation_id="test-conversation-id",
        device_id="test-device-id",
        satellite_id=None,
        language="en",
        agent_id=entity.entity_id,
        extra_system_prompt="Be helpful",
    )

    assert user_input.conversation_id is not None
    chat_log = conversation.ChatLog(hass, user_input.conversation_id)
    chat_log.async_add_user_content(conversation.UserContent(content=user_input.text))
    mock_provide_llm_data = AsyncMock()
    object.__setattr__(chat_log, "async_provide_llm_data", mock_provide_llm_data)

    async def fake_handle_chat_log(log):
        """Inject assistant output."""
        assert log is chat_log
        log.async_add_assistant_content_without_tools(
            conversation.AssistantContent(
                agent_id=entity.entity_id,
                content="Turning on the lights",
            )
        )

    with patch.object(
        entity, "_async_handle_chat_log", side_effect=fake_handle_chat_log
    ) as mock_handle:
        result = await entity._async_handle_message(user_input, chat_log)

    # Verify async_provide_llm_data was called correctly
    mock_provide_llm_data.assert_awaited_once_with(
        user_input.as_llm_context(DOMAIN),
        [llm.LLM_API_ASSIST],
        "You are a helpful assistant.",
        "Be helpful",
    )

    # Verify _async_handle_chat_log was called
    mock_handle.assert_awaited_once_with(chat_log)

    # Verify result
    assert result.conversation_id == "test-conversation-id"
    assert result.response.speech["plain"]["speech"] == "Turning on the lights"


async def test_async_handle_message_converse_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test message handling when ConverseError is raised."""
    mock_config_entry.add_to_hass(hass)
    subentry = next(iter(mock_config_entry.subentries.values()))

    with patch.object(
        mock_config_entry, "runtime_data", create=True
    ) as mock_runtime_data:
        mock_runtime_data.client = AsyncMock()
        entity = AWSBedrockConversationEntity(mock_config_entry, subentry)
        entity.hass = hass
        entity.entity_id = "conversation.aws_bedrock_test"

    user_input = conversation.ConversationInput(
        text="Hello",
        context=Context(),
        conversation_id="test-conversation-id",
        device_id=None,
        satellite_id=None,
        language="en",
        agent_id=entity.entity_id,
    )

    assert user_input.conversation_id is not None
    chat_log = conversation.ChatLog(hass, user_input.conversation_id)

    # Create a ConverseError to simulate an error
    error_response = intent.IntentResponse(language="en")
    converse_error = conversation.ConverseError(
        "Test error", user_input.conversation_id or "", error_response
    )
    object.__setattr__(
        chat_log, "async_provide_llm_data", AsyncMock(side_effect=converse_error)
    )

    with patch.object(
        entity, "_async_handle_chat_log", AsyncMock()
    ) as mock_handle_chat_log:
        result = await entity._async_handle_message(user_input, chat_log)

    # Verify _async_handle_chat_log was NOT called due to error
    mock_handle_chat_log.assert_not_called()

    # Verify error result
    assert result.response is error_response
    assert result.conversation_id == user_input.conversation_id


async def test_async_handle_message_unexpected_exception_in_provide_llm_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test message handling when unexpected exception is raised in async_provide_llm_data."""
    mock_config_entry.add_to_hass(hass)
    subentry = next(iter(mock_config_entry.subentries.values()))

    with patch.object(
        mock_config_entry, "runtime_data", create=True
    ) as mock_runtime_data:
        mock_runtime_data.client = AsyncMock()
        entity = AWSBedrockConversationEntity(mock_config_entry, subentry)
        entity.hass = hass
        entity.entity_id = "conversation.aws_bedrock_test"

    user_input = conversation.ConversationInput(
        text="Hello",
        context=Context(),
        conversation_id="test-conversation-id",
        device_id=None,
        satellite_id=None,
        language="en",
        agent_id=entity.entity_id,
    )

    assert user_input.conversation_id is not None
    chat_log = conversation.ChatLog(hass, user_input.conversation_id)

    # Raise an unexpected exception
    object.__setattr__(
        chat_log,
        "async_provide_llm_data",
        AsyncMock(side_effect=ValueError("Unexpected error")),
    )

    with (
        patch.object(
            entity, "_async_handle_chat_log", AsyncMock()
        ) as mock_handle_chat_log,
        pytest.raises(ValueError, match="Unexpected error"),
    ):
        await entity._async_handle_message(user_input, chat_log)

    # Verify _async_handle_chat_log was NOT called due to error
    mock_handle_chat_log.assert_not_called()


async def test_async_handle_message_exception_in_handle_chat_log(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test message handling when exception is raised in _async_handle_chat_log."""
    mock_config_entry.add_to_hass(hass)
    subentry = next(iter(mock_config_entry.subentries.values()))

    with patch.object(
        mock_config_entry, "runtime_data", create=True
    ) as mock_runtime_data:
        mock_runtime_data.client = AsyncMock()
        entity = AWSBedrockConversationEntity(mock_config_entry, subentry)
        entity.hass = hass
        entity.entity_id = "conversation.aws_bedrock_test"

    user_input = conversation.ConversationInput(
        text="Hello",
        context=Context(),
        conversation_id="test-conversation-id",
        device_id=None,
        satellite_id=None,
        language="en",
        agent_id=entity.entity_id,
    )

    assert user_input.conversation_id is not None
    chat_log = conversation.ChatLog(hass, user_input.conversation_id)
    chat_log.async_add_user_content(conversation.UserContent(content=user_input.text))
    object.__setattr__(chat_log, "async_provide_llm_data", AsyncMock())

    # Make _async_handle_chat_log raise an exception
    with (
        patch.object(
            entity,
            "_async_handle_chat_log",
            AsyncMock(side_effect=RuntimeError("Chat log error")),
        ),
        pytest.raises(RuntimeError, match="Chat log error"),
    ):
        await entity._async_handle_message(user_input, chat_log)
