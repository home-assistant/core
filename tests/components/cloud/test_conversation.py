"""Tests for the Home Assistant Cloud conversation entity."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components import conversation
from homeassistant.components.cloud.const import DOMAIN
from homeassistant.components.cloud.conversation import CloudConversationEntity
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent, llm

from tests.common import MockConfigEntry


@pytest.fixture
def cloud_conversation_entity(hass: HomeAssistant) -> CloudConversationEntity:
    """Return a CloudConversationEntity attached to hass."""
    cloud = MagicMock()
    cloud.llm = MagicMock()
    cloud.is_logged_in = True
    cloud.valid_subscription = True
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    entity = CloudConversationEntity(cloud, entry)
    entity.entity_id = "conversation.home_assistant_cloud"
    entity.hass = hass
    return entity


def test_entity_availability(
    cloud_conversation_entity: CloudConversationEntity,
) -> None:
    """Test that availability mirrors the cloud login/subscription state."""
    cloud_conversation_entity._cloud.is_logged_in = True
    cloud_conversation_entity._cloud.valid_subscription = True
    assert cloud_conversation_entity.available

    cloud_conversation_entity._cloud.is_logged_in = False
    assert not cloud_conversation_entity.available

    cloud_conversation_entity._cloud.is_logged_in = True
    cloud_conversation_entity._cloud.valid_subscription = False
    assert not cloud_conversation_entity.available


async def test_async_handle_message(
    hass: HomeAssistant, cloud_conversation_entity: CloudConversationEntity
) -> None:
    """Test that messages are processed through the chat log helper."""
    user_input = conversation.ConversationInput(
        text="apaga test",
        context=Context(),
        conversation_id="conversation-id",
        device_id="device-id",
        satellite_id=None,
        language="es",
        agent_id=cloud_conversation_entity.entity_id or "",
        extra_system_prompt="hazlo",
    )
    chat_log = conversation.ChatLog(hass, user_input.conversation_id)
    chat_log.async_add_user_content(conversation.UserContent(content=user_input.text))
    chat_log.async_provide_llm_data = AsyncMock()

    async def fake_handle(chat_type, log):
        """Inject assistant output so the result can be built."""
        assert chat_type == "conversation"
        assert log is chat_log
        log.async_add_assistant_content_without_tools(
            conversation.AssistantContent(
                agent_id=cloud_conversation_entity.entity_id or "",
                content="hecho",
            )
        )

    handle_chat_log = AsyncMock(side_effect=fake_handle)

    with patch.object(
        cloud_conversation_entity, "_async_handle_chat_log", handle_chat_log
    ):
        result = await cloud_conversation_entity._async_handle_message(
            user_input, chat_log
        )

    chat_log.async_provide_llm_data.assert_awaited_once_with(
        user_input.as_llm_context(DOMAIN),
        llm.LLM_API_ASSIST,
        None,
        user_input.extra_system_prompt,
    )
    handle_chat_log.assert_awaited_once_with("conversation", chat_log)
    assert result.conversation_id == "conversation-id"
    assert result.response.speech["plain"]["speech"] == "hecho"


async def test_async_handle_message_converse_error(
    hass: HomeAssistant, cloud_conversation_entity: CloudConversationEntity
) -> None:
    """Test that ConverseError short-circuits message handling."""
    user_input = conversation.ConversationInput(
        text="hola",
        context=Context(),
        conversation_id="conversation-id",
        device_id=None,
        satellite_id=None,
        language="es",
        agent_id=cloud_conversation_entity.entity_id or "",
    )
    chat_log = conversation.ChatLog(hass, user_input.conversation_id)

    error_response = intent.IntentResponse(language="es")
    converse_error = conversation.ConverseError(
        "failed", user_input.conversation_id or "", error_response
    )
    chat_log.async_provide_llm_data = AsyncMock(side_effect=converse_error)

    with patch.object(
        cloud_conversation_entity, "_async_handle_chat_log", AsyncMock()
    ) as handle_chat_log:
        result = await cloud_conversation_entity._async_handle_message(
            user_input, chat_log
        )

    handle_chat_log.assert_not_called()
    assert result.response is error_response
    assert result.conversation_id == user_input.conversation_id
