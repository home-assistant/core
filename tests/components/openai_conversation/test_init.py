"""Tests for the OpenAI integration."""

from unittest.mock import AsyncMock, mock_open, patch
import json
from httpx import Response
from openai import (
    APIConnectionError,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
)
from openai.types.image import Image
from openai.types.images_response import ImagesResponse
from openai.types.chat.chat_completion import ChatCompletion, Choice
from openai.types.chat.chat_completion_message import ChatCompletionMessage
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


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
    ("service_name", "error"),
    [
        ("generate_image", "Invalid config entry provided. Got invalid_entry"),
        ("generate_content", "Invalid config entry provided. Got invalid_entry"),
    ],
)
async def test_invalid_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    service_name: str,
    error: str,
) -> None:
    """Assert exception when invalid config entry is provided."""
    service_data = {
        "prompt": "Picture of a dog",
        "config_entry": "invalid_entry",
    }
    with pytest.raises(ServiceValidationError, match=error):
        await hass.services.async_call(
            "openai_conversation",
            service_name,
            service_data,
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
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    side_effect,
    error,
) -> None:
    """Test initialization errors."""
    with patch(
        "openai.resources.models.AsyncModels.list",
        side_effect=side_effect,
    ):
        assert await async_setup_component(hass, "openai_conversation", {})
        await hass.async_block_till_done()
        assert error in caplog.text


@pytest.mark.parametrize(
    ("service_data", "expected_args", "number_of_files"),
    [
        (
            {"prompt": "Picture of a dog"},
            {
                "messages": [
                    {
                        "content": [
                            {
                                "type": "text",
                                "text": "Picture of a dog",
                            },
                        ],
                    },
                ],
            },
            0,
        ),
        (
            {"prompt": "Picture of a dog", "image_filename": ["/a/b/c.jpg"]},
            {
                "messages": [
                    {
                        "content": [
                            {
                                "type": "text",
                                "text": "Picture of a dog",
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": "data:image/jpeg;base64,BASE64IMAGE1",
                                },
                            },
                        ],
                    },
                ],
            },
            1,
        ),
        (
            {
                "prompt": "Picture of a dog",
                "image_filename": ["/a/b/c.jpg", "d/e/f.jpg"],
            },
            {
                "messages": [
                    {
                        "content": [
                            {
                                "type": "text",
                                "text": "Picture of a dog",
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": "data:image/jpeg;base64,BASE64IMAGE1",
                                },
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": "data:image/jpeg;base64,BASE64IMAGE2",
                                },
                            },
                        ],
                    },
                ],
            },
            2,
        ),
    ],
)
async def test_generate_content_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    service_data,
    expected_args,
    number_of_files,
) -> None:
    """Test generate content service."""
    service_data["config_entry"] = mock_config_entry.entry_id
    expected_args["model"] = "gpt-4o-mini"
    expected_args["n"] = 1
    expected_args["response_format"] = {"type": "json_object"}
    expected_args["messages"][0]["role"] = "user"

    with (
        patch(
            "openai.resources.chat.completions.AsyncCompletions.create",
            new_callable=AsyncMock,
        ) as mock_create,
        patch(
            "base64.b64encode", side_effect=[b"BASE64IMAGE1", b"BASE64IMAGE2"]
        ) as mock_b64encode,
        patch("builtins.open", mock_open(read_data="ABC")) as mock_file,
    ):
        mock_create.return_value = ChatCompletion(
            id="",
            model="",
            created=1700000000,
            object="chat.completion",
            choices=[
                Choice(
                    index=0,
                    finish_reason="stop",
                    message=ChatCompletionMessage(
                        role="assistant",
                        content="This is the response",
                    ),
                )
            ],
        )

        response = await hass.services.async_call(
            "openai_conversation",
            "generate_content",
            service_data,
            blocking=True,
            return_response=True,
        )
        print(response)
        assert response == {"text": "This is the response"}
        assert len(mock_create.mock_calls) == 1
        assert mock_create.mock_calls[0][2] == expected_args
        assert mock_b64encode.call_count == number_of_files
        if "image_filename" in service_data:
            for idx, file in enumerate(service_data["image_filename"]):
                assert mock_file.call_args_list[idx][0][0] == file


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_content_service_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test generate content service handles errors."""
    with (
        patch(
            "openai.resources.chat.completions.AsyncCompletions.create",
            side_effect=RateLimitError(
                response=Response(status_code=None, request=""),
                body=None,
                message="Reason",
            ),
        ),
        pytest.raises(HomeAssistantError, match="Error generating content: Reason"),
    ):
        await hass.services.async_call(
            "openai_conversation",
            "generate_content",
            {
                "config_entry": mock_config_entry.entry_id,
                "prompt": "Image of an epic fail",
            },
            blocking=True,
            return_response=True,
        )
