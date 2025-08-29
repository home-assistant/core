"""Tests for the OpenAI integration."""

from typing import Any
from unittest.mock import AsyncMock, Mock, mock_open, patch

import httpx
from openai import (
    APIConnectionError,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
)
from openai.types.image import Image
from openai.types.images_response import ImagesResponse
from openai.types.responses import Response, ResponseOutputMessage, ResponseOutputText
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.openai_conversation import CONF_CHAT_MODEL
from homeassistant.components.openai_conversation.const import (
    DEFAULT_AI_TASK_NAME,
    DEFAULT_CONVERSATION_NAME,
    DOMAIN,
    RECOMMENDED_AI_TASK_OPTIONS,
    RECOMMENDED_CONVERSATION_OPTIONS,
)
from homeassistant.config_entries import ConfigEntryDisabler, ConfigSubentryData
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryDisabler
from homeassistant.helpers.entity_registry import RegistryEntryDisabler
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
        new_callable=AsyncMock,
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
            new_callable=AsyncMock,
            side_effect=RateLimitError(
                response=httpx.Response(
                    status_code=500, request=httpx.Request(method="GET", url="")
                ),
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

    with (
        patch(
            "openai.resources.images.AsyncImages.generate",
            new_callable=AsyncMock,
            return_value=ImagesResponse(
                created=1700000000,
                data=[
                    Image(
                        b64_json=None,
                        revised_prompt=None,
                        url=None,
                    )
                ],
            ),
        ),
        pytest.raises(HomeAssistantError, match="No image returned"),
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


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_content_service_with_image_not_allowed_path(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test generate content service with an image in a not allowed path."""
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch.object(hass.config, "is_allowed_path", return_value=False),
        pytest.raises(
            HomeAssistantError,
            match=(
                "Cannot read `doorbell_snapshot.jpg`, no access to path; "
                "`allowlist_external_dirs` may need to be adjusted in "
                "`configuration.yaml`"
            ),
        ),
    ):
        await hass.services.async_call(
            "openai_conversation",
            "generate_content",
            {
                "config_entry": mock_config_entry.entry_id,
                "prompt": "Describe this image from my doorbell camera",
                "filenames": "doorbell_snapshot.jpg",
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
        (
            APIConnectionError(request=httpx.Request(method="GET", url="test")),
            "Connection error",
        ),
        (
            AuthenticationError(
                response=httpx.Response(
                    status_code=500, request=httpx.Request(method="GET", url="test")
                ),
                body=None,
                message="",
            ),
            "Invalid API key",
        ),
        (
            BadRequestError(
                response=httpx.Response(
                    status_code=500, request=httpx.Request(method="GET", url="test")
                ),
                body=None,
                message="",
            ),
            "openai_conversation integration not ready yet",
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
            {"prompt": "Picture of a dog", "filenames": []},
            {
                "input": [
                    {
                        "content": [
                            {
                                "type": "input_text",
                                "text": "Picture of a dog",
                            },
                        ],
                    },
                ],
            },
            0,
        ),
        (
            {"prompt": "Picture of a dog", "filenames": ["/a/b/c.pdf"]},
            {
                "input": [
                    {
                        "content": [
                            {
                                "type": "input_text",
                                "text": "Picture of a dog",
                            },
                            {
                                "type": "input_file",
                                "file_data": "data:application/pdf;base64,BASE64IMAGE1",
                                "filename": "/a/b/c.pdf",
                            },
                        ],
                    },
                ],
            },
            1,
        ),
        (
            {"prompt": "Picture of a dog", "filenames": ["/a/b/c.jpg"]},
            {
                "input": [
                    {
                        "content": [
                            {
                                "type": "input_text",
                                "text": "Picture of a dog",
                            },
                            {
                                "type": "input_image",
                                "image_url": "data:image/jpeg;base64,BASE64IMAGE1",
                                "detail": "auto",
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
                "filenames": ["/a/b/c.jpg", "d/e/f.jpg"],
            },
            {
                "input": [
                    {
                        "content": [
                            {
                                "type": "input_text",
                                "text": "Picture of a dog",
                            },
                            {
                                "type": "input_image",
                                "image_url": "data:image/jpeg;base64,BASE64IMAGE1",
                                "detail": "auto",
                            },
                            {
                                "type": "input_image",
                                "image_url": "data:image/jpeg;base64,BASE64IMAGE2",
                                "detail": "auto",
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
    expected_args["max_output_tokens"] = 3000
    expected_args["top_p"] = 1.0
    expected_args["temperature"] = 1.0
    expected_args["user"] = None
    expected_args["store"] = False
    expected_args["input"][0]["type"] = "message"
    expected_args["input"][0]["role"] = "user"

    with (
        patch(
            "openai.resources.responses.AsyncResponses.create",
            new_callable=AsyncMock,
        ) as mock_create,
        patch(
            "base64.b64encode", side_effect=[b"BASE64IMAGE1", b"BASE64IMAGE2"]
        ) as mock_b64encode,
        patch("pathlib.Path.read_bytes", Mock(return_value=b"ABC")) as mock_file,
        patch("pathlib.Path.exists", return_value=True),
        patch.object(hass.config, "is_allowed_path", return_value=True),
    ):
        mock_create.return_value = Response(
            object="response",
            id="resp_A",
            created_at=1700000000,
            model="gpt-4o-mini",
            parallel_tool_calls=True,
            tool_choice="auto",
            tools=[],
            output=[
                ResponseOutputMessage(
                    type="message",
                    id="msg_A",
                    content=[
                        ResponseOutputText(
                            type="output_text",
                            text="This is the response",
                            annotations=[],
                        )
                    ],
                    role="assistant",
                    status="completed",
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
        assert response == {"text": "This is the response"}
        assert len(mock_create.mock_calls) == 1
        assert mock_create.mock_calls[0][2] == expected_args
        assert mock_b64encode.call_count == number_of_files
        assert mock_file.call_count == number_of_files


@pytest.mark.parametrize(
    (
        "service_data",
        "error",
        "exists_side_effect",
        "is_allowed_side_effect",
    ),
    [
        (
            {"prompt": "Picture of a dog", "filenames": ["/a/b/c.jpg"]},
            "`/a/b/c.jpg` does not exist",
            [False],
            [True],
        ),
        (
            {
                "prompt": "Picture of a dog",
                "filenames": ["/a/b/c.jpg", "d/e/f.png"],
            },
            "Cannot read `d/e/f.png`, no access to path; `allowlist_external_dirs` may need to be adjusted in `configuration.yaml`",
            [True, True],
            [True, False],
        ),
        (
            {"prompt": "Not a picture of a dog", "filenames": ["/a/b/c.mov"]},
            "Only images and PDF are supported by the OpenAI API,`/a/b/c.mov` is not an image file or PDF",
            [True],
            [True],
        ),
    ],
)
async def test_generate_content_service_invalid(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    service_data,
    error,
    exists_side_effect,
    is_allowed_side_effect,
) -> None:
    """Test generate content service."""
    service_data["config_entry"] = mock_config_entry.entry_id

    with (
        patch(
            "openai.resources.responses.AsyncResponses.create",
            new_callable=AsyncMock,
        ) as mock_create,
        patch("base64.b64encode", side_effect=[b"BASE64IMAGE1", b"BASE64IMAGE2"]),
        patch("builtins.open", mock_open(read_data="ABC")),
        patch("pathlib.Path.exists", side_effect=exists_side_effect),
        patch.object(
            hass.config, "is_allowed_path", side_effect=is_allowed_side_effect
        ),
    ):
        with pytest.raises(HomeAssistantError, match=error):
            await hass.services.async_call(
                "openai_conversation",
                "generate_content",
                service_data,
                blocking=True,
                return_response=True,
            )
        assert len(mock_create.mock_calls) == 0


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_content_service_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test generate content service handles errors."""
    with (
        patch(
            "openai.resources.responses.AsyncResponses.create",
            side_effect=RateLimitError(
                response=httpx.Response(
                    status_code=417, request=httpx.Request(method="GET", url="")
                ),
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


async def test_migration_from_v1(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration from version 1 to version 2."""
    # Create a v1 config entry with conversation options and an entity
    OPTIONS = {
        "recommended": True,
        "llm_hass_api": ["assist"],
        "prompt": "You are a helpful assistant",
        "chat_model": "gpt-4o-mini",
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "1234"},
        options=OPTIONS,
        version=1,
        title="ChatGPT",
    )
    mock_config_entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.entry_id)},
        name=mock_config_entry.title,
        manufacturer="OpenAI",
        model="ChatGPT",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity = entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry.entry_id,
        config_entry=mock_config_entry,
        device_id=device.id,
        suggested_object_id="chatgpt",
    )

    # Run migration
    with patch(
        "homeassistant.components.openai_conversation.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.version == 2
    assert mock_config_entry.minor_version == 4
    assert mock_config_entry.data == {"api_key": "1234"}
    assert mock_config_entry.options == {}

    assert len(mock_config_entry.subentries) == 2

    # Find the conversation subentry
    conversation_subentry = None
    ai_task_subentry = None
    for subentry in mock_config_entry.subentries.values():
        if subentry.subentry_type == "conversation":
            conversation_subentry = subentry
        elif subentry.subentry_type == "ai_task_data":
            ai_task_subentry = subentry
    assert conversation_subentry is not None
    assert conversation_subentry.unique_id is None
    assert conversation_subentry.title == "ChatGPT"
    assert conversation_subentry.subentry_type == "conversation"
    assert conversation_subentry.data == OPTIONS

    assert ai_task_subentry is not None
    assert ai_task_subentry.unique_id is None
    assert ai_task_subentry.title == DEFAULT_AI_TASK_NAME
    assert ai_task_subentry.subentry_type == "ai_task_data"

    # Use conversation subentry for the rest of the assertions
    subentry = conversation_subentry

    migrated_entity = entity_registry.async_get(entity.entity_id)
    assert migrated_entity is not None
    assert migrated_entity.config_entry_id == mock_config_entry.entry_id
    assert migrated_entity.config_subentry_id == subentry.subentry_id
    assert migrated_entity.unique_id == subentry.subentry_id

    # Check device migration
    assert not device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )
    assert (
        migrated_device := device_registry.async_get_device(
            identifiers={(DOMAIN, subentry.subentry_id)}
        )
    )
    assert migrated_device.identifiers == {(DOMAIN, subentry.subentry_id)}
    assert migrated_device.id == device.id
    assert migrated_device.config_entries == {mock_config_entry.entry_id}
    assert migrated_device.config_entries_subentries == {
        mock_config_entry.entry_id: {subentry.subentry_id}
    }


async def test_migration_from_v1_with_multiple_keys(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration from version 1 with different API keys."""
    # Create two v1 config entries with different API keys
    options = {
        "recommended": True,
        "llm_hass_api": ["assist"],
        "prompt": "You are a helpful assistant",
        "chat_model": "gpt-4o-mini",
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "1234"},
        options=options,
        version=1,
        title="ChatGPT 1",
    )
    mock_config_entry.add_to_hass(hass)
    mock_config_entry_2 = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "12345"},
        options=options,
        version=1,
        title="ChatGPT 2",
    )
    mock_config_entry_2.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.entry_id)},
        name=mock_config_entry.title,
        manufacturer="OpenAI",
        model="ChatGPT 1",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry.entry_id,
        config_entry=mock_config_entry,
        device_id=device.id,
        suggested_object_id="chatgpt_1",
    )

    device_2 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry_2.entry_id,
        identifiers={(DOMAIN, mock_config_entry_2.entry_id)},
        name=mock_config_entry_2.title,
        manufacturer="OpenAI",
        model="ChatGPT 2",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry_2.entry_id,
        config_entry=mock_config_entry_2,
        device_id=device_2.id,
        suggested_object_id="chatgpt_2",
    )

    # Run migration
    with patch(
        "homeassistant.components.openai_conversation.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2

    for idx, entry in enumerate(entries):
        assert entry.version == 2
        assert entry.minor_version == 4
        assert not entry.options
        assert len(entry.subentries) == 2

        conversation_subentry = None
        for subentry in entry.subentries.values():
            if subentry.subentry_type == "conversation":
                conversation_subentry = subentry
                break

        assert conversation_subentry is not None
        assert conversation_subentry.subentry_type == "conversation"
        assert conversation_subentry.data == options
        assert conversation_subentry.title == f"ChatGPT {idx + 1}"

        # Use conversation subentry for device assertions
        subentry = conversation_subentry

        dev = device_registry.async_get_device(
            identifiers={(DOMAIN, subentry.subentry_id)}
        )
        assert dev is not None
        assert dev.config_entries == {entry.entry_id}
        assert dev.config_entries_subentries == {entry.entry_id: {subentry.subentry_id}}


async def test_migration_from_v1_with_same_keys(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration from version 1 with same API keys consolidates entries."""
    # Create two v1 config entries with the same API key
    options = {
        "recommended": True,
        "llm_hass_api": ["assist"],
        "prompt": "You are a helpful assistant",
        "chat_model": "gpt-4o-mini",
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "1234"},
        options=options,
        version=1,
        title="ChatGPT",
    )
    mock_config_entry.add_to_hass(hass)
    mock_config_entry_2 = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "1234"},  # Same API key
        options=options,
        version=1,
        title="ChatGPT 2",
    )
    mock_config_entry_2.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.entry_id)},
        name=mock_config_entry.title,
        manufacturer="OpenAI",
        model="ChatGPT",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry.entry_id,
        config_entry=mock_config_entry,
        device_id=device.id,
        suggested_object_id="chatgpt",
    )

    device_2 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry_2.entry_id,
        identifiers={(DOMAIN, mock_config_entry_2.entry_id)},
        name=mock_config_entry_2.title,
        manufacturer="OpenAI",
        model="ChatGPT",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry_2.entry_id,
        config_entry=mock_config_entry_2,
        device_id=device_2.id,
        suggested_object_id="chatgpt_2",
    )

    # Run migration
    with patch(
        "homeassistant.components.openai_conversation.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        await hass.async_block_till_done()

    # Should have only one entry left (consolidated)
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    entry = entries[0]
    assert entry.version == 2
    assert entry.minor_version == 4
    assert not entry.options
    assert (
        len(entry.subentries) == 3
    )  # Two conversation subentries + one AI task subentry

    # Check both conversation subentries exist with correct data
    conversation_subentries = [
        sub for sub in entry.subentries.values() if sub.subentry_type == "conversation"
    ]
    ai_task_subentries = [
        sub for sub in entry.subentries.values() if sub.subentry_type == "ai_task_data"
    ]

    assert len(conversation_subentries) == 2
    assert len(ai_task_subentries) == 1

    titles = [sub.title for sub in conversation_subentries]
    assert "ChatGPT" in titles
    assert "ChatGPT 2" in titles

    for subentry in conversation_subentries:
        assert subentry.subentry_type == "conversation"
        assert subentry.data == options

        # Check devices were migrated correctly
        dev = device_registry.async_get_device(
            identifiers={(DOMAIN, subentry.subentry_id)}
        )
        assert dev is not None
        assert dev.config_entries == {mock_config_entry.entry_id}
        assert dev.config_entries_subentries == {
            mock_config_entry.entry_id: {subentry.subentry_id}
        }


@pytest.mark.parametrize(
    (
        "config_entry_disabled_by",
        "device_disabled_by",
        "entity_disabled_by",
        "merged_config_entry_disabled_by",
        "conversation_subentry_data",
        "main_config_entry",
    ),
    [
        (
            [ConfigEntryDisabler.USER, None],
            [DeviceEntryDisabler.CONFIG_ENTRY, None],
            [RegistryEntryDisabler.CONFIG_ENTRY, None],
            None,
            [
                {
                    "conversation_entity_id": "conversation.chatgpt_2",
                    "device_disabled_by": None,
                    "entity_disabled_by": None,
                    "device": 1,
                },
                {
                    "conversation_entity_id": "conversation.chatgpt",
                    "device_disabled_by": DeviceEntryDisabler.USER,
                    "entity_disabled_by": RegistryEntryDisabler.DEVICE,
                    "device": 0,
                },
            ],
            1,
        ),
        (
            [None, ConfigEntryDisabler.USER],
            [None, DeviceEntryDisabler.CONFIG_ENTRY],
            [None, RegistryEntryDisabler.CONFIG_ENTRY],
            None,
            [
                {
                    "conversation_entity_id": "conversation.chatgpt",
                    "device_disabled_by": None,
                    "entity_disabled_by": None,
                    "device": 0,
                },
                {
                    "conversation_entity_id": "conversation.chatgpt_2",
                    "device_disabled_by": DeviceEntryDisabler.USER,
                    "entity_disabled_by": RegistryEntryDisabler.DEVICE,
                    "device": 1,
                },
            ],
            0,
        ),
        (
            [ConfigEntryDisabler.USER, ConfigEntryDisabler.USER],
            [DeviceEntryDisabler.CONFIG_ENTRY, DeviceEntryDisabler.CONFIG_ENTRY],
            [RegistryEntryDisabler.CONFIG_ENTRY, RegistryEntryDisabler.CONFIG_ENTRY],
            ConfigEntryDisabler.USER,
            [
                {
                    "conversation_entity_id": "conversation.chatgpt",
                    "device_disabled_by": DeviceEntryDisabler.CONFIG_ENTRY,
                    "entity_disabled_by": RegistryEntryDisabler.CONFIG_ENTRY,
                    "device": 0,
                },
                {
                    "conversation_entity_id": "conversation.chatgpt_2",
                    "device_disabled_by": DeviceEntryDisabler.CONFIG_ENTRY,
                    "entity_disabled_by": RegistryEntryDisabler.CONFIG_ENTRY,
                    "device": 1,
                },
            ],
            0,
        ),
    ],
)
async def test_migration_from_v1_disabled(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry_disabled_by: list[ConfigEntryDisabler | None],
    device_disabled_by: list[DeviceEntryDisabler | None],
    entity_disabled_by: list[RegistryEntryDisabler | None],
    merged_config_entry_disabled_by: ConfigEntryDisabler | None,
    conversation_subentry_data: list[dict[str, Any]],
    main_config_entry: int,
) -> None:
    """Test migration where the config entries are disabled."""
    # Create a v1 config entry with conversation options and an entity
    options = {
        "recommended": True,
        "llm_hass_api": ["assist"],
        "prompt": "You are a helpful assistant",
        "chat_model": "gpt-4o-mini",
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "1234"},
        options=options,
        version=1,
        title="ChatGPT",
        disabled_by=config_entry_disabled_by[0],
    )
    mock_config_entry.add_to_hass(hass)
    mock_config_entry_2 = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "1234"},
        options=options,
        version=1,
        title="ChatGPT 2",
        disabled_by=config_entry_disabled_by[1],
    )
    mock_config_entry_2.add_to_hass(hass)
    mock_config_entries = [mock_config_entry, mock_config_entry_2]

    device_1 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.entry_id)},
        name=mock_config_entry.title,
        manufacturer="OpenAI",
        model="ChatGPT",
        entry_type=dr.DeviceEntryType.SERVICE,
        disabled_by=device_disabled_by[0],
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry.entry_id,
        config_entry=mock_config_entry,
        device_id=device_1.id,
        suggested_object_id="chatgpt",
        disabled_by=entity_disabled_by[0],
    )

    device_2 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry_2.entry_id,
        identifiers={(DOMAIN, mock_config_entry_2.entry_id)},
        name=mock_config_entry_2.title,
        manufacturer="OpenAI",
        model="ChatGPT",
        entry_type=dr.DeviceEntryType.SERVICE,
        disabled_by=device_disabled_by[1],
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry_2.entry_id,
        config_entry=mock_config_entry_2,
        device_id=device_2.id,
        suggested_object_id="chatgpt_2",
        disabled_by=entity_disabled_by[1],
    )

    devices = [device_1, device_2]

    # Run migration
    with patch(
        "homeassistant.components.openai_conversation.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.disabled_by is merged_config_entry_disabled_by
    assert entry.version == 2
    assert entry.minor_version == 4
    assert not entry.options
    assert entry.title == "OpenAI Conversation"
    assert len(entry.subentries) == 3
    conversation_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "conversation"
    ]
    assert len(conversation_subentries) == 2
    for subentry in conversation_subentries:
        assert subentry.subentry_type == "conversation"
        assert subentry.data == options
        assert "ChatGPT" in subentry.title
    ai_task_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "ai_task_data"
    ]
    assert len(ai_task_subentries) == 1
    assert ai_task_subentries[0].data == RECOMMENDED_AI_TASK_OPTIONS
    assert ai_task_subentries[0].title == DEFAULT_AI_TASK_NAME

    assert not device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )
    assert not device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry_2.entry_id)}
    )

    for idx, subentry in enumerate(conversation_subentries):
        subentry_data = conversation_subentry_data[idx]
        entity = entity_registry.async_get(subentry_data["conversation_entity_id"])
        assert entity.unique_id == subentry.subentry_id
        assert entity.config_subentry_id == subentry.subentry_id
        assert entity.config_entry_id == entry.entry_id
        assert entity.disabled_by is subentry_data["entity_disabled_by"]

        assert (
            device := device_registry.async_get_device(
                identifiers={(DOMAIN, subentry.subentry_id)}
            )
        )
        assert device.identifiers == {(DOMAIN, subentry.subentry_id)}
        assert device.id == devices[subentry_data["device"]].id
        assert device.config_entries == {
            mock_config_entries[main_config_entry].entry_id
        }
        assert device.config_entries_subentries == {
            mock_config_entries[main_config_entry].entry_id: {subentry.subentry_id}
        }
        assert device.disabled_by is subentry_data["device_disabled_by"]


async def test_migration_from_v2_1(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration from version 2.1.

    This tests we clean up the broken migration in Home Assistant Core
    2025.7.0b0-2025.7.0b1:
    - Fix device registry (Fixed in Home Assistant Core 2025.7.0b2)
    """
    # Create a v2.1 config entry with 2 subentries, devices and entities
    options = {
        "recommended": True,
        "llm_hass_api": ["assist"],
        "prompt": "You are a helpful assistant",
        "chat_model": "gpt-4o-mini",
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "1234"},
        entry_id="mock_entry_id",
        version=2,
        minor_version=1,
        subentries_data=[
            ConfigSubentryData(
                data=options,
                subentry_id="mock_id_1",
                subentry_type="conversation",
                title="ChatGPT",
                unique_id=None,
            ),
            ConfigSubentryData(
                data=options,
                subentry_id="mock_id_2",
                subentry_type="conversation",
                title="ChatGPT 2",
                unique_id=None,
            ),
        ],
        title="ChatGPT",
    )
    mock_config_entry.add_to_hass(hass)

    device_1 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        config_subentry_id="mock_id_1",
        identifiers={(DOMAIN, "mock_id_1")},
        name="ChatGPT",
        manufacturer="OpenAI",
        model="ChatGPT",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    device_1 = device_registry.async_update_device(
        device_1.id, add_config_entry_id="mock_entry_id", add_config_subentry_id=None
    )
    assert device_1.config_entries_subentries == {"mock_entry_id": {None, "mock_id_1"}}
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        "mock_id_1",
        config_entry=mock_config_entry,
        config_subentry_id="mock_id_1",
        device_id=device_1.id,
        suggested_object_id="chatgpt",
    )

    device_2 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        config_subentry_id="mock_id_2",
        identifiers={(DOMAIN, "mock_id_2")},
        name="ChatGPT 2",
        manufacturer="OpenAI",
        model="ChatGPT",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        "mock_id_2",
        config_entry=mock_config_entry,
        config_subentry_id="mock_id_2",
        device_id=device_2.id,
        suggested_object_id="chatgpt_2",
    )

    # Run migration
    with patch(
        "homeassistant.components.openai_conversation.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.version == 2
    assert entry.minor_version == 4
    assert not entry.options
    assert entry.title == "ChatGPT"
    assert len(entry.subentries) == 3  # 2 conversation + 1 AI task
    conversation_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "conversation"
    ]
    ai_task_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "ai_task_data"
    ]
    assert len(conversation_subentries) == 2
    assert len(ai_task_subentries) == 1
    for subentry in conversation_subentries:
        assert subentry.subentry_type == "conversation"
        assert subentry.data == options
        assert "ChatGPT" in subentry.title

    subentry = conversation_subentries[0]

    entity = entity_registry.async_get("conversation.chatgpt")
    assert entity.unique_id == subentry.subentry_id
    assert entity.config_subentry_id == subentry.subentry_id
    assert entity.config_entry_id == entry.entry_id

    assert not device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )
    assert (
        device := device_registry.async_get_device(
            identifiers={(DOMAIN, subentry.subentry_id)}
        )
    )
    assert device.identifiers == {(DOMAIN, subentry.subentry_id)}
    assert device.id == device_1.id
    assert device.config_entries == {mock_config_entry.entry_id}
    assert device.config_entries_subentries == {
        mock_config_entry.entry_id: {subentry.subentry_id}
    }

    subentry = conversation_subentries[1]

    entity = entity_registry.async_get("conversation.chatgpt_2")
    assert entity.unique_id == subentry.subentry_id
    assert entity.config_subentry_id == subentry.subentry_id
    assert entity.config_entry_id == entry.entry_id
    assert not device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )
    assert (
        device := device_registry.async_get_device(
            identifiers={(DOMAIN, subentry.subentry_id)}
        )
    )
    assert device.identifiers == {(DOMAIN, subentry.subentry_id)}
    assert device.id == device_2.id
    assert device.config_entries == {mock_config_entry.entry_id}
    assert device.config_entries_subentries == {
        mock_config_entry.entry_id: {subentry.subentry_id}
    }


@pytest.mark.parametrize(
    "mock_conversation_subentry_data", [{}, {CONF_CHAT_MODEL: "gpt-1o"}]
)
async def test_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test devices are correctly created for subentries."""
    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(devices) == 2  # One for conversation, one for AI task

    # Use the first device for snapshot comparison
    device = devices[0]
    assert device == snapshot(exclude=props("identifiers"))
    # Verify the device has identifiers matching one of the subentries
    expected_identifiers = [
        {(DOMAIN, subentry.subentry_id)}
        for subentry in mock_config_entry.subentries.values()
    ]
    assert device.identifiers in expected_identifiers


async def test_migration_from_v2_2(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration from version 2.2."""
    # Create a v2.2 config entry with a conversation subentry
    options = {
        "recommended": True,
        "llm_hass_api": ["assist"],
        "prompt": "You are a helpful assistant",
        "chat_model": "gpt-4o-mini",
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "1234"},
        entry_id="mock_entry_id",
        version=2,
        minor_version=2,
        subentries_data=[
            ConfigSubentryData(
                data=options,
                subentry_id="mock_id_1",
                subentry_type="conversation",
                title="ChatGPT",
                unique_id=None,
            ),
        ],
        title="ChatGPT",
    )
    mock_config_entry.add_to_hass(hass)

    # Run migration
    with patch(
        "homeassistant.components.openai_conversation.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.version == 2
    assert entry.minor_version == 4
    assert not entry.options
    assert entry.title == "ChatGPT"
    assert len(entry.subentries) == 2

    # Check conversation subentry is still there
    conversation_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "conversation"
    ]
    assert len(conversation_subentries) == 1
    conversation_subentry = conversation_subentries[0]
    assert conversation_subentry.data == options

    # Check AI Task subentry was added
    ai_task_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "ai_task_data"
    ]
    assert len(ai_task_subentries) == 1
    ai_task_subentry = ai_task_subentries[0]
    assert ai_task_subentry.data == {"recommended": True}
    assert ai_task_subentry.title == "OpenAI AI Task"


@pytest.mark.parametrize(
    (
        "config_entry_disabled_by",
        "device_disabled_by",
        "entity_disabled_by",
        "setup_result",
        "minor_version_after_migration",
        "config_entry_disabled_by_after_migration",
        "device_disabled_by_after_migration",
        "entity_disabled_by_after_migration",
    ),
    [
        # Config entry not disabled, update device and entity disabled by config entry
        (
            None,
            DeviceEntryDisabler.CONFIG_ENTRY,
            RegistryEntryDisabler.CONFIG_ENTRY,
            True,
            4,
            None,
            DeviceEntryDisabler.USER,
            RegistryEntryDisabler.DEVICE,
        ),
        (
            None,
            DeviceEntryDisabler.USER,
            RegistryEntryDisabler.DEVICE,
            True,
            4,
            None,
            DeviceEntryDisabler.USER,
            RegistryEntryDisabler.DEVICE,
        ),
        (
            None,
            DeviceEntryDisabler.USER,
            RegistryEntryDisabler.USER,
            True,
            4,
            None,
            DeviceEntryDisabler.USER,
            RegistryEntryDisabler.USER,
        ),
        (
            None,
            None,
            None,
            True,
            4,
            None,
            None,
            None,
        ),
        # Config entry disabled, migration does not run
        (
            ConfigEntryDisabler.USER,
            DeviceEntryDisabler.CONFIG_ENTRY,
            RegistryEntryDisabler.CONFIG_ENTRY,
            False,
            3,
            ConfigEntryDisabler.USER,
            DeviceEntryDisabler.CONFIG_ENTRY,
            RegistryEntryDisabler.CONFIG_ENTRY,
        ),
        (
            ConfigEntryDisabler.USER,
            DeviceEntryDisabler.USER,
            RegistryEntryDisabler.DEVICE,
            False,
            3,
            ConfigEntryDisabler.USER,
            DeviceEntryDisabler.USER,
            RegistryEntryDisabler.DEVICE,
        ),
        (
            ConfigEntryDisabler.USER,
            DeviceEntryDisabler.USER,
            RegistryEntryDisabler.USER,
            False,
            3,
            ConfigEntryDisabler.USER,
            DeviceEntryDisabler.USER,
            RegistryEntryDisabler.USER,
        ),
        (
            ConfigEntryDisabler.USER,
            None,
            None,
            False,
            3,
            ConfigEntryDisabler.USER,
            None,
            None,
        ),
    ],
)
async def test_migrate_entry_from_v2_3(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry_disabled_by: ConfigEntryDisabler | None,
    device_disabled_by: DeviceEntryDisabler | None,
    entity_disabled_by: RegistryEntryDisabler | None,
    setup_result: bool,
    minor_version_after_migration: int,
    config_entry_disabled_by_after_migration: ConfigEntryDisabler | None,
    device_disabled_by_after_migration: ConfigEntryDisabler | None,
    entity_disabled_by_after_migration: RegistryEntryDisabler | None,
) -> None:
    """Test migration from version 2.3."""
    # Create a v2.3 config entry with conversation subentries
    conversation_subentry_id = "blabla"
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-api-key"},
        disabled_by=config_entry_disabled_by,
        version=2,
        minor_version=3,
        subentries_data=[
            {
                "data": RECOMMENDED_CONVERSATION_OPTIONS,
                "subentry_id": conversation_subentry_id,
                "subentry_type": "conversation",
                "title": DEFAULT_CONVERSATION_NAME,
                "unique_id": None,
            },
        ],
    )
    mock_config_entry.add_to_hass(hass)

    conversation_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        config_subentry_id=conversation_subentry_id,
        disabled_by=device_disabled_by,
        identifiers={(DOMAIN, mock_config_entry.entry_id)},
        name=mock_config_entry.title,
        manufacturer="OpenAI",
        model="ChatGPT",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    conversation_entity = entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry.entry_id,
        config_entry=mock_config_entry,
        config_subentry_id=conversation_subentry_id,
        disabled_by=entity_disabled_by,
        device_id=conversation_device.id,
        suggested_object_id="chatgpt",
    )

    # Verify initial state
    assert mock_config_entry.version == 2
    assert mock_config_entry.minor_version == 3
    assert len(mock_config_entry.subentries) == 1
    assert mock_config_entry.disabled_by == config_entry_disabled_by
    assert conversation_device.disabled_by == device_disabled_by
    assert conversation_entity.disabled_by == entity_disabled_by

    # Run setup to trigger migration
    with patch(
        "homeassistant.components.openai_conversation.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        assert result is setup_result
        await hass.async_block_till_done()

    # Verify migration completed
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]

    # Check version and subversion were updated
    assert entry.version == 2
    assert entry.minor_version == minor_version_after_migration

    # Check the disabled_by flag on config entry, device and entity are as expected
    conversation_device = device_registry.async_get(conversation_device.id)
    conversation_entity = entity_registry.async_get(conversation_entity.entity_id)
    assert mock_config_entry.disabled_by == config_entry_disabled_by_after_migration
    assert conversation_device.disabled_by == device_disabled_by_after_migration
    assert conversation_entity.disabled_by == entity_disabled_by_after_migration
