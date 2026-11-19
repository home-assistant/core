"""Tests for the Code Mode preview feature in conversations."""

import pytest

from homeassistant.components.conversation import (
    AssistantContent,
    ConversationInput,
    SystemContent,
    async_get_chat_log,
)
from homeassistant.components.labs import async_update_preview_feature
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import chat_session, llm
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
async def setup_integrations(hass: HomeAssistant) -> None:
    """Set up the integrations that a conversation needs."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "labs", {})
    assert await async_setup_component(hass, "conversation", {})


async def _tool_names(
    hass: HomeAssistant, conversation_id: str | None = None
) -> list[str]:
    """Return the names of the tools that a conversation agent gets."""
    return [tool.name for tool in (await _llm_data(hass, conversation_id))[0]]


async def _llm_data(
    hass: HomeAssistant, conversation_id: str | None = None
) -> tuple[list[llm.Tool], str, str]:
    """Return the tools, the system prompt and the conversation ID of an agent."""
    user_input = ConversationInput(
        text="Hello",
        context=Context(),
        conversation_id=conversation_id,
        agent_id="mock-agent-id",
        device_id=None,
        satellite_id=None,
        language="en",
    )
    with (
        chat_session.async_get_chat_session(
            hass, conversation_id, context=None
        ) as session,
        async_get_chat_log(hass, session, user_input) as chat_log,
    ):
        await chat_log.async_provide_llm_data(
            user_input.as_llm_context("test"), llm.LLM_API_ASSIST
        )
        assert chat_log.llm_api is not None
        chat_log.async_add_assistant_content_without_tools(
            AssistantContent(agent_id="mock-agent-id", content="Hi")
        )
        system_prompt = chat_log.content[0]
        assert isinstance(system_prompt, SystemContent)
        return chat_log.llm_api.tools, system_prompt.content, session.conversation_id


async def test_feature_disabled(hass: HomeAssistant) -> None:
    """Test the agent gets the tools."""
    assert "llm__GetDateTime" in await _tool_names(hass)


async def test_feature_enabled(hass: HomeAssistant) -> None:
    """Test the agent gets the execute tool in place of the tools."""
    await async_update_preview_feature(hass, "llm", "code_mode", True)

    assert await _tool_names(hass) == ["execute"]

    await async_update_preview_feature(hass, "llm", "code_mode", False)

    assert "llm__GetDateTime" in await _tool_names(hass)


async def test_toggle_in_conversation(hass: HomeAssistant) -> None:
    """Test a change of the feature applies to a conversation that continues."""
    tools, _, conversation_id = await _llm_data(hass)
    assert "llm__GetDateTime" in [tool.name for tool in tools]

    # The chat log keeps the tools of a conversation that continues.
    same_tools, _, same_conversation_id = await _llm_data(hass, conversation_id)
    assert same_conversation_id == conversation_id
    assert same_tools is tools

    await async_update_preview_feature(hass, "llm", "code_mode", True)

    assert await _tool_names(hass, conversation_id) == ["execute"]

    await async_update_preview_feature(hass, "llm", "code_mode", False)

    assert "llm__GetDateTime" in await _tool_names(hass, conversation_id)


async def test_date_time_prompt(hass: HomeAssistant) -> None:
    """Test the prompt has no fixed time when code can get the time."""
    assert "Current time is" not in (await _llm_data(hass))[1]

    await async_update_preview_feature(hass, "llm", "code_mode", True)

    _, prompt, _ = await _llm_data(hass)
    assert "async def llm__GetDateTime() -> dict:" in prompt
    assert "Current time is" not in prompt
