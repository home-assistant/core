"""Tests for the OpenAI integration."""

from unittest.mock import AsyncMock, patch

from httpx import Response
from openai import (
    APIConnectionError,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
)
from openai.types.chat.chat_completion import ChatCompletion, Choice
from openai.types.chat.chat_completion_message import ChatCompletionMessage
from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
    Function,
)
from openai.types.completion_usage import CompletionUsage
from openai.types.image import Image
from openai.types.images_response import ImagesResponse
import pytest
import voluptuous as vol

from homeassistant.components import conversation
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import intent, llm
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@patch("homeassistant.components.openai_conversation.conversation.llm.async_get_tools")
@patch("homeassistant.components.openai_conversation.conversation.llm.async_call_tool")
async def test_function_call(
    mock_call_tool,
    mock_get_tools,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test function call from the assistant."""
    entry = MockConfigEntry(title=None)
    entry.add_to_hass(hass)

    mock_call_tool.return_value = "Test response"

    mock_tool = llm.Tool()
    mock_tool.name = "test_tool"
    mock_tool.description = "Test function"
    mock_tool.parameters = vol.Schema(
        {vol.Optional("param1", description="Test parameters"): str}
    )

    mock_get_tools.return_value = [mock_tool]

    def completion_result(*args, messages, **kwargs):
        for message in messages:
            role = message["role"] if isinstance(message, dict) else message.role
            if role == "tool":
                return ChatCompletion(
                    id="chatcmpl-1234567890ZYXWVUTSRQPONMLKJIH",
                    choices=[
                        Choice(
                            finish_reason="stop",
                            index=0,
                            message=ChatCompletionMessage(
                                content="I have successfully called the function",
                                role="assistant",
                                function_call=None,
                                tool_calls=None,
                            ),
                        )
                    ],
                    created=1700000000,
                    model="gpt-4-1106-preview",
                    object="chat.completion",
                    system_fingerprint=None,
                    usage=CompletionUsage(
                        completion_tokens=9, prompt_tokens=8, total_tokens=17
                    ),
                )

        return ChatCompletion(
            id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
            choices=[
                Choice(
                    finish_reason="tool_calls",
                    index=0,
                    message=ChatCompletionMessage(
                        content=None,
                        role="assistant",
                        function_call=None,
                        tool_calls=[
                            ChatCompletionMessageToolCall(
                                id="call_AbCdEfGhIjKlMnOpQrStUvWx",
                                function=Function(
                                    arguments='{"param1":"test_value"}',
                                    name="test_tool",
                                ),
                                type="function",
                            )
                        ],
                    ),
                )
            ],
            created=1700000000,
            model="gpt-4-1106-preview",
            object="chat.completion",
            system_fingerprint=None,
            usage=CompletionUsage(
                completion_tokens=9, prompt_tokens=8, total_tokens=17
            ),
        )

    context = Context()

    with patch(
        "openai.resources.chat.completions.AsyncCompletions.create",
        new_callable=AsyncMock,
        side_effect=completion_result,
    ) as mock_create:
        result = await conversation.async_converse(
            hass,
            "Please call the test function",
            None,
            context,
            agent_id=mock_config_entry.entry_id,
        )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert mock_create.mock_calls[1][2]["messages"][3] == {
        "role": "tool",
        "tool_call_id": "call_AbCdEfGhIjKlMnOpQrStUvWx",
        "name": "test_tool",
        "content": '"Test response"',
    }
    mock_call_tool.assert_awaited_once_with(
        hass,
        llm.ToolInput(
            tool_name="test_tool",
            tool_args={"param1": "test_value"},
            platform="openai_conversation",
            context=context,
            user_prompt="Please call the test function",
            language="en",
            assistant="conversation",
        ),
    )


@patch("homeassistant.components.openai_conversation.conversation.llm.async_get_tools")
@patch("homeassistant.components.openai_conversation.conversation.llm.async_call_tool")
async def test_function_exception(
    mock_call_tool,
    mock_get_tools,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test function call with exception."""
    entry = MockConfigEntry(title=None)
    entry.add_to_hass(hass)

    mock_call_tool.side_effect = RuntimeError("Test tool exception")

    mock_tool = llm.Tool()
    mock_tool.name = "test_tool"
    mock_tool.description = "Test function"
    mock_tool.parameters = vol.Schema(
        {vol.Optional("param1", description="Test parameters"): str}
    )

    mock_get_tools.return_value = [mock_tool]

    def completion_result(*args, messages, **kwargs):
        for message in messages:
            role = message["role"] if isinstance(message, dict) else message.role
            if role == "tool":
                return ChatCompletion(
                    id="chatcmpl-1234567890ZYXWVUTSRQPONMLKJIH",
                    choices=[
                        Choice(
                            finish_reason="stop",
                            index=0,
                            message=ChatCompletionMessage(
                                content="There was an error calling the function",
                                role="assistant",
                                function_call=None,
                                tool_calls=None,
                            ),
                        )
                    ],
                    created=1700000000,
                    model="gpt-4-1106-preview",
                    object="chat.completion",
                    system_fingerprint=None,
                    usage=CompletionUsage(
                        completion_tokens=9, prompt_tokens=8, total_tokens=17
                    ),
                )

        return ChatCompletion(
            id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
            choices=[
                Choice(
                    finish_reason="tool_calls",
                    index=0,
                    message=ChatCompletionMessage(
                        content=None,
                        role="assistant",
                        function_call=None,
                        tool_calls=[
                            ChatCompletionMessageToolCall(
                                id="call_AbCdEfGhIjKlMnOpQrStUvWx",
                                function=Function(
                                    arguments='{"param1":"test_value"}',
                                    name="test_tool",
                                ),
                                type="function",
                            )
                        ],
                    ),
                )
            ],
            created=1700000000,
            model="gpt-4-1106-preview",
            object="chat.completion",
            system_fingerprint=None,
            usage=CompletionUsage(
                completion_tokens=9, prompt_tokens=8, total_tokens=17
            ),
        )

    context = Context()

    with patch(
        "openai.resources.chat.completions.AsyncCompletions.create",
        new_callable=AsyncMock,
        side_effect=completion_result,
    ) as mock_create:
        result = await conversation.async_converse(
            hass,
            "Please call the test function",
            None,
            context,
            agent_id=mock_config_entry.entry_id,
        )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert mock_create.mock_calls[1][2]["messages"][3] == {
        "role": "tool",
        "tool_call_id": "call_AbCdEfGhIjKlMnOpQrStUvWx",
        "name": "test_tool",
        "content": '{"error": "RuntimeError", "error_text": "Test tool exception"}',
    }
    mock_call_tool.assert_awaited_once_with(
        hass,
        llm.ToolInput(
            tool_name="test_tool",
            tool_args={"param1": "test_value"},
            platform="openai_conversation",
            context=context,
            user_prompt="Please call the test function",
            language="en",
            assistant="conversation",
        ),
    )


@pytest.mark.parametrize(
    ("service_data", "expected_args"),
    [
        (
            {"prompt": "Picture of a dog"},
            {
                "prompt": "Picture of a dog",
                "size": "1024x1024",
                "quality": "standard",
                "style": "vivid",
            },
        ),
        (
            {
                "prompt": "Picture of a dog",
                "size": "1024x1792",
                "quality": "hd",
                "style": "vivid",
            },
            {
                "prompt": "Picture of a dog",
                "size": "1024x1792",
                "quality": "hd",
                "style": "vivid",
            },
        ),
        (
            {
                "prompt": "Picture of a dog",
                "size": "1792x1024",
                "quality": "standard",
                "style": "natural",
            },
            {
                "prompt": "Picture of a dog",
                "size": "1792x1024",
                "quality": "standard",
                "style": "natural",
            },
        ),
        (
            {"prompt": "Picture of a dog", "size": "256"},
            {
                "prompt": "Picture of a dog",
                "size": "1024x1024",
                "quality": "standard",
                "style": "vivid",
            },
        ),
        (
            {"prompt": "Picture of a dog", "size": "512"},
            {
                "prompt": "Picture of a dog",
                "size": "1024x1024",
                "quality": "standard",
                "style": "vivid",
            },
        ),
        (
            {"prompt": "Picture of a dog", "size": "1024"},
            {
                "prompt": "Picture of a dog",
                "size": "1024x1024",
                "quality": "standard",
                "style": "vivid",
            },
        ),
    ],
)
async def test_generate_image_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    service_data,
    expected_args,
) -> None:
    """Test generate image service."""
    service_data["config_entry"] = mock_config_entry.entry_id
    expected_args["model"] = "dall-e-3"
    expected_args["response_format"] = "url"
    expected_args["n"] = 1

    with patch(
        "openai.resources.images.AsyncImages.generate",
        return_value=ImagesResponse(
            created=1700000000,
            data=[
                Image(
                    b64_json=None,
                    revised_prompt="A clear and detailed picture of an ordinary canine",
                    url="A",
                )
            ],
        ),
    ) as mock_create:
        response = await hass.services.async_call(
            "openai_conversation",
            "generate_image",
            service_data,
            blocking=True,
            return_response=True,
        )

    assert response == {
        "url": "A",
        "revised_prompt": "A clear and detailed picture of an ordinary canine",
    }
    assert len(mock_create.mock_calls) == 1
    assert mock_create.mock_calls[0][2] == expected_args


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_image_service_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test generate image service handles errors."""
    with (
        patch(
            "openai.resources.images.AsyncImages.generate",
            side_effect=RateLimitError(
                response=Response(status_code=None, request=""),
                body=None,
                message="Reason",
            ),
        ),
        pytest.raises(HomeAssistantError, match="Error generating image: Reason"),
    ):
        await hass.services.async_call(
            "openai_conversation",
            "generate_image",
            {
                "config_entry": mock_config_entry.entry_id,
                "prompt": "Image of an epic fail",
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (APIConnectionError(request=None), "Connection error"),
        (
            AuthenticationError(
                response=Response(status_code=None, request=""), body=None, message=None
            ),
            "Invalid API key",
        ),
        (
            BadRequestError(
                response=Response(status_code=None, request=""), body=None, message=None
            ),
            "openai_conversation integration not ready yet: None",
        ),
    ],
)
async def test_init_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, caplog, side_effect, error
) -> None:
    """Test initialization errors."""
    with patch(
        "openai.resources.models.AsyncModels.list",
        side_effect=side_effect,
    ):
        assert await async_setup_component(hass, "openai_conversation", {})
        await hass.async_block_till_done()
        assert error in caplog.text
