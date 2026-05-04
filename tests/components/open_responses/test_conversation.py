"""Tests for Open Responses conversation."""

from collections.abc import AsyncGenerator
from copy import deepcopy
from typing import Any
from unittest.mock import patch

from homeassistant.components import conversation
from homeassistant.components.open_responses.const import (
    CONF_BASE_URL,
    CONF_GENERATED_DEFAULT_SUBENTRY,
    DEFAULT_CONVERSATION_NAME,
    DOMAIN,
    RECOMMENDED_CONVERSATION_OPTIONS,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_API_KEY, CONF_MODEL
from homeassistant.core import Context, HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


def _mock_response_stream(calls: list[dict[str, Any]], text: str) -> Any:
    """Return a streaming response mock."""

    async def stream_response(**params: Any) -> AsyncGenerator[dict[str, Any]]:
        calls.append(deepcopy(params))
        yield {
            "type": "response.output_item.added",
            "item": {
                "type": "message",
                "id": "msg_1",
                "role": "assistant",
                "content": [],
                "status": "in_progress",
            },
        }
        yield {"type": "response.output_text.delta", "delta": text}
        yield {
            "type": "response.output_item.done",
            "item": {
                "type": "message",
                "id": "msg_1",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text}],
                "status": "completed",
            },
        }
        yield {
            "type": "response.completed",
            "response": {"usage": {"input_tokens": 1, "output_tokens": 1}},
        }

    return stream_response


async def test_conversation_turn(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
) -> None:
    """Test a conversation turn reaches the Open Responses client."""
    calls: list[dict[str, Any]] = []
    mock_config_entry.runtime_data.stream_response = _mock_response_stream(
        calls, "Hello from Open Responses"
    )

    result = await conversation.async_converse(
        hass,
        "hello",
        None,
        Context(),
        agent_id=mock_config_entry.entry_id,
    )

    assert result.response.speech["plain"]["speech"] == "Hello from Open Responses"
    assert calls[0]["model"] == "open-responses-model"
    assert calls[0]["input"][-1] == {
        "type": "message",
        "role": "user",
        "content": "hello",
    }


async def test_only_generated_default_subentry_registers_entry_agent(
    hass: HomeAssistant,
) -> None:
    """Test custom subentries do not override the config-entry agent."""
    entry = MockConfigEntry(
        title="Open Responses",
        domain=DOMAIN,
        data={
            CONF_API_KEY: "bla",
            CONF_BASE_URL: "https://example.local/v1",
            CONF_MODEL: "open-responses-model",
        },
        subentries_data=[
            ConfigSubentryData(
                data={
                    **RECOMMENDED_CONVERSATION_OPTIONS,
                    CONF_GENERATED_DEFAULT_SUBENTRY: True,
                    CONF_MODEL: "open-responses-model",
                },
                subentry_type="conversation",
                title=DEFAULT_CONVERSATION_NAME,
                unique_id=None,
            ),
            ConfigSubentryData(
                data={
                    **RECOMMENDED_CONVERSATION_OPTIONS,
                    CONF_MODEL: "open-responses-model",
                },
                subentry_type="conversation",
                title=DEFAULT_CONVERSATION_NAME,
                unique_id=None,
            ),
        ],
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.open_responses.conversation.conversation.async_set_agent"
    ) as mock_set_agent:
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    assert mock_set_agent.call_count == 1
    assert mock_set_agent.call_args.args[1] is entry
