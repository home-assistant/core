"""Tests for the Ollama conversation integration."""

from unittest.mock import AsyncMock, patch

from httpx import ConnectError
from ollama import Message, ResponseError
import pytest

from homeassistant.components import conversation, ollama_conversation
from homeassistant.const import MATCH_ALL
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_chat(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_init_component
) -> None:
    """Test that the chat function is called with the appropriate arguments."""
    with patch(
        "ollama.AsyncClient.chat",
        return_value={"message": {"role": "assistant", "content": "test response"}},
    ) as mock_chat:
        result = await conversation.async_converse(
            hass,
            "test message",
            None,
            Context(),
            agent_id=mock_config_entry.entry_id,
        )

        assert mock_chat.call_count == 1
        args = mock_chat.call_args.kwargs
        assert args["model"] == "test model"
        assert args["options"] == {"test option": "test value"}
        assert args["messages"] == [
            Message({"role": "system", "content": "test prompt"}),
            Message({"role": "user", "content": "test message"}),
        ]

        assert (
            result.response.response_type == intent.IntentResponseType.ACTION_DONE
        ), result
        assert result.response.speech["plain"]["speech"] == "test response"


async def test_message_history_trimming(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_init_component
) -> None:
    """Test that a single message history is trimmed according to the config."""
    response_idx = 0

    def response(*args, **kwargs) -> dict:
        nonlocal response_idx
        response_idx += 1
        return {"message": {"role": "assistant", "content": f"response {response_idx}"}}

    with patch(
        "ollama.AsyncClient.chat",
        side_effect=response,
    ) as mock_chat:
        # mock_init_component sets "max_history" to 2
        for i in range(5):
            result = await conversation.async_converse(
                hass,
                f"message {i+1}",
                conversation_id="1234",
                context=Context(),
                agent_id=mock_config_entry.entry_id,
            )
            assert (
                result.response.response_type == intent.IntentResponseType.ACTION_DONE
            ), result

        assert mock_chat.call_count == 5
        args = mock_chat.call_args_list

        # system + user-1
        assert len(args[0].kwargs["messages"]) == 2
        assert args[0].kwargs["messages"][1]["content"] == "message 1"

        # Full history
        # system + user-1 + assistant-1 + user-2
        assert len(args[1].kwargs["messages"]) == 4
        assert args[1].kwargs["messages"][0]["role"] == "system"
        assert args[1].kwargs["messages"][0]["content"] == "test prompt"
        assert args[1].kwargs["messages"][1]["role"] == "user"
        assert args[1].kwargs["messages"][1]["content"] == "message 1"
        assert args[1].kwargs["messages"][2]["role"] == "assistant"
        assert args[1].kwargs["messages"][2]["content"] == "response 1"
        assert args[1].kwargs["messages"][3]["role"] == "user"
        assert args[1].kwargs["messages"][3]["content"] == "message 2"

        # Full history
        # system + user-1 + assistant-1 + user-2 + assistant-2 + user-3
        assert len(args[2].kwargs["messages"]) == 6
        assert args[2].kwargs["messages"][0]["role"] == "system"
        assert args[2].kwargs["messages"][0]["content"] == "test prompt"
        assert args[2].kwargs["messages"][1]["role"] == "user"
        assert args[2].kwargs["messages"][1]["content"] == "message 1"
        assert args[2].kwargs["messages"][2]["role"] == "assistant"
        assert args[2].kwargs["messages"][2]["content"] == "response 1"
        assert args[2].kwargs["messages"][3]["role"] == "user"
        assert args[2].kwargs["messages"][3]["content"] == "message 2"
        assert args[2].kwargs["messages"][4]["role"] == "assistant"
        assert args[2].kwargs["messages"][4]["content"] == "response 2"
        assert args[2].kwargs["messages"][5]["role"] == "user"
        assert args[2].kwargs["messages"][5]["content"] == "message 3"

        # Trimmed down to two user messages.
        # system + user-2 + assistant-2 + user-3 + assistant-3 + user-4
        assert len(args[3].kwargs["messages"]) == 6
        assert args[3].kwargs["messages"][0]["role"] == "system"
        assert args[3].kwargs["messages"][0]["content"] == "test prompt"
        assert args[3].kwargs["messages"][1]["role"] == "user"
        assert args[3].kwargs["messages"][1]["content"] == "message 2"
        assert args[3].kwargs["messages"][2]["role"] == "assistant"
        assert args[3].kwargs["messages"][2]["content"] == "response 2"
        assert args[3].kwargs["messages"][3]["role"] == "user"
        assert args[3].kwargs["messages"][3]["content"] == "message 3"
        assert args[3].kwargs["messages"][4]["role"] == "assistant"
        assert args[3].kwargs["messages"][4]["content"] == "response 3"
        assert args[3].kwargs["messages"][5]["role"] == "user"
        assert args[3].kwargs["messages"][5]["content"] == "message 4"

        # Trimmed down to two user messages.
        # system + user-3 + assistant-3 + user-4 + assistant-4 + user-5
        assert len(args[3].kwargs["messages"]) == 6
        assert args[4].kwargs["messages"][0]["role"] == "system"
        assert args[4].kwargs["messages"][0]["content"] == "test prompt"
        assert args[4].kwargs["messages"][1]["role"] == "user"
        assert args[4].kwargs["messages"][1]["content"] == "message 3"
        assert args[4].kwargs["messages"][2]["role"] == "assistant"
        assert args[4].kwargs["messages"][2]["content"] == "response 3"
        assert args[4].kwargs["messages"][3]["role"] == "user"
        assert args[4].kwargs["messages"][3]["content"] == "message 4"
        assert args[4].kwargs["messages"][4]["role"] == "assistant"
        assert args[4].kwargs["messages"][4]["content"] == "response 4"
        assert args[4].kwargs["messages"][5]["role"] == "user"
        assert args[4].kwargs["messages"][5]["content"] == "message 5"


async def test_message_history_pruning(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_init_component
) -> None:
    """Test that old message histories are pruned."""
    with patch(
        "ollama.AsyncClient.chat",
        return_value={"message": {"role": "assistant", "content": "test response"}},
    ):
        # Create 3 different message histories
        conversation_ids: list[str] = []
        for i in range(3):
            result = await conversation.async_converse(
                hass,
                f"message {i+1}",
                conversation_id=None,
                context=Context(),
                agent_id=mock_config_entry.entry_id,
            )
            assert (
                result.response.response_type == intent.IntentResponseType.ACTION_DONE
            ), result
            assert isinstance(result.conversation_id, str)
            conversation_ids.append(result.conversation_id)

        agent = await conversation._get_agent_manager(hass).async_get_agent(
            mock_config_entry.entry_id
        )
        assert isinstance(agent, ollama_conversation.OllamaAgent)
        assert len(agent._history) == 3
        assert agent._history.keys() == set(conversation_ids)

        # Modify the timestamps of the first 2 histories so they will be pruned
        # on the next cycle.
        for conversation_id in conversation_ids[:2]:
            # Move back 2 hours
            agent._history[conversation_id].timestamp -= 2 * 60 * 60

        # Next cycle
        result = await conversation.async_converse(
            hass,
            "test message",
            conversation_id=None,
            context=Context(),
            agent_id=mock_config_entry.entry_id,
        )
        assert (
            result.response.response_type == intent.IntentResponseType.ACTION_DONE
        ), result

        # Only the most recent histories should remain
        assert len(agent._history) == 2
        assert conversation_ids[-1] in agent._history
        assert result.conversation_id in agent._history


async def test_message_history_unlimited(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_init_component
) -> None:
    """Test that message history is not trimmed when max_history = 0."""
    conversation_id = "1234"
    with (
        patch(
            "ollama.AsyncClient.chat",
            return_value={"message": {"role": "assistant", "content": "test response"}},
        ),
        patch.object(
            mock_config_entry, "options", {ollama_conversation.CONF_MAX_HISTORY: 0}
        ),
    ):
        for i in range(100):
            result = await conversation.async_converse(
                hass,
                f"message {i+1}",
                conversation_id=conversation_id,
                context=Context(),
                agent_id=mock_config_entry.entry_id,
            )
            assert (
                result.response.response_type == intent.IntentResponseType.ACTION_DONE
            ), result

        agent = await conversation._get_agent_manager(hass).async_get_agent(
            mock_config_entry.entry_id
        )
        assert isinstance(agent, ollama_conversation.OllamaAgent)

        assert len(agent._history) == 1
        assert conversation_id in agent._history
        assert agent._history[conversation_id].num_user_messages == 100


async def test_error_handling(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_init_component
) -> None:
    """Test error handling during converse."""
    with patch(
        "ollama.AsyncClient.chat",
        new_callable=AsyncMock,
        side_effect=ResponseError("test error"),
    ):
        result = await conversation.async_converse(
            hass, "hello", None, Context(), agent_id=mock_config_entry.entry_id
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
    assert result.response.error_code == "unknown", result


async def test_template_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that template error handling works."""
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            "prompt": "talk like a {% if True %}smarthome{% else %}pirate please.",
        },
    )
    with patch(
        "ollama.AsyncClient.list",
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        result = await conversation.async_converse(
            hass, "hello", None, Context(), agent_id=mock_config_entry.entry_id
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
    assert result.response.error_code == "unknown", result


async def test_conversation_agent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test OllamaAgent."""
    agent = await conversation._get_agent_manager(hass).async_get_agent(
        mock_config_entry.entry_id
    )
    assert agent.supported_languages == MATCH_ALL


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (ConnectError(message="Connect error"), "Connect error"),
        (RuntimeError("Runtime error"), "Runtime error"),
    ],
)
async def test_init_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, caplog, side_effect, error
) -> None:
    """Test initialization errors."""
    with patch(
        "ollama.AsyncClient.list",
        side_effect=side_effect,
    ):
        assert await async_setup_component(hass, ollama_conversation.DOMAIN, {})
        await hass.async_block_till_done()
        assert error in caplog.text
