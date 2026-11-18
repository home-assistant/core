"""Tests for the Code Mode preview feature in conversations."""

from unittest.mock import patch

import pytest

from homeassistant.components.conversation import ConversationInput, async_get_chat_log
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


async def _tool_names(hass: HomeAssistant) -> list[str]:
    """Return the names of the tools that a conversation agent gets."""
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
            user_input.as_llm_context("test"), llm.LLM_API_ASSIST
        )
        assert chat_log.llm_api is not None
        return [tool.name for tool in chat_log.llm_api.tools]


async def test_feature_disabled(hass: HomeAssistant) -> None:
    """Test the agent gets the tools and Code Mode stays unloaded."""
    assert "llm__GetDateTime" in await _tool_names(hass)
    assert "code_mode" not in hass.config.components


async def test_feature_enabled(hass: HomeAssistant) -> None:
    """Test the agent gets the execute tool in place of the tools."""
    await async_update_preview_feature(hass, "code_mode", "code_mode", True)

    assert await _tool_names(hass) == ["execute"]
    assert "code_mode" in hass.config.components

    await async_update_preview_feature(hass, "code_mode", "code_mode", False)

    assert "llm__GetDateTime" in await _tool_names(hass)


async def test_setup_fails(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the agent gets the tools when the sandbox cannot start."""
    await async_update_preview_feature(hass, "code_mode", "code_mode", True)

    with patch(
        "homeassistant.components.code_mode.AsyncMonty", autospec=True
    ) as mock_pool:
        mock_pool.return_value.__aenter__.side_effect = OSError("No binary")
        assert "llm__GetDateTime" in await _tool_names(hass)

    assert "Code mode cannot be set up" in caplog.text
