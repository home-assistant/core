"""Tests for code mode in conversations."""

from typing import override

import pytest

from homeassistant.components.conversation import (
    ConversationInput,
    SystemContent,
    async_get_chat_log,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import chat_session, llm
from homeassistant.setup import async_setup_component


class OtherAPI(llm.API):
    """API without tools that is not the Assist API."""

    @override
    async def async_get_api_instance(
        self, llm_context: llm.LLMContext
    ) -> llm.APIInstance:
        """Return the instance of the API."""
        return llm.APIInstance(
            api=self, api_prompt="", llm_context=llm_context, tools=[]
        )


@pytest.fixture(autouse=True)
async def setup_integrations(hass: HomeAssistant) -> None:
    """Set up the integrations that a conversation needs and a second API."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    llm.async_register_api(hass, OtherAPI(hass=hass, id="other", name="Other"))


async def _llm_data(
    hass: HomeAssistant, api_ids: str | list[str], *, code_mode: bool = True
) -> tuple[list[str], str]:
    """Return the tool names and the system prompt that an agent gets."""
    user_input = ConversationInput(
        text="Hello",
        context=Context(),
        conversation_id=None,
        agent_id="mock-agent-id",
        device_id=None,
        satellite_id=None,
        language="en",
    )
    with (
        chat_session.async_get_chat_session(hass, context=None) as session,
        async_get_chat_log(hass, session, user_input) as chat_log,
    ):
        await chat_log.async_provide_llm_data(
            user_input.as_llm_context("test"), api_ids, code_mode=code_mode
        )
        assert chat_log.llm_api is not None
        system_prompt = chat_log.content[0]
        assert isinstance(system_prompt, SystemContent)
        return [tool.name for tool in chat_log.llm_api.tools], system_prompt.content


@pytest.mark.parametrize("api_ids", [llm.LLM_API_ASSIST, [llm.LLM_API_ASSIST]])
async def test_assist_only(hass: HomeAssistant, api_ids: str | list[str]) -> None:
    """Test the agent gets the tools when Assist is the only API."""
    tool_names, _ = await _llm_data(hass, api_ids)

    assert "llm__GetDateTime" in tool_names
    assert "execute" not in tool_names


@pytest.mark.parametrize("api_ids", ["other", [llm.LLM_API_ASSIST, "other"]])
async def test_other_apis(hass: HomeAssistant, api_ids: str | list[str]) -> None:
    """Test the agent gets the code mode tools when it has another API."""
    tool_names, _ = await _llm_data(hass, api_ids)

    assert tool_names == ["search", "execute"]


async def test_code_mode_disabled(hass: HomeAssistant) -> None:
    """Test an agent can get the tools of other APIs directly."""
    tool_names, _ = await _llm_data(
        hass, [llm.LLM_API_ASSIST, "other"], code_mode=False
    )

    assert "llm__GetDateTime" in tool_names
    assert "execute" not in tool_names


async def test_date_time_prompt(hass: HomeAssistant) -> None:
    """Test the prompt has no fixed time when code can get the time."""
    _, prompt = await _llm_data(hass, [llm.LLM_API_ASSIST, "other"])
    assert "Current time is" not in prompt

    _, prompt = await _llm_data(hass, "other")
    assert "Current time is" in prompt
