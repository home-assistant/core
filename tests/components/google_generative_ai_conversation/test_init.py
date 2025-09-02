"""Tests for the Google Generative AI Conversation integration."""

from typing import Any
from unittest.mock import AsyncMock, Mock, mock_open, patch

from google.genai.types import File, FileState
import pytest
from requests.exceptions import Timeout
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.google_generative_ai_conversation.const import (
    DEFAULT_AI_TASK_NAME,
    DEFAULT_CONVERSATION_NAME,
    DEFAULT_STT_NAME,
    DEFAULT_TITLE,
    DEFAULT_TTS_NAME,
    DOMAIN,
    RECOMMENDED_AI_TASK_OPTIONS,
    RECOMMENDED_CONVERSATION_OPTIONS,
    RECOMMENDED_STT_OPTIONS,
    RECOMMENDED_TTS_OPTIONS,
)
from homeassistant.config_entries import (
    ConfigEntryDisabler,
    ConfigEntryState,
    ConfigSubentryData,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryDisabler
from homeassistant.helpers.entity_registry import RegistryEntryDisabler

from . import API_ERROR_500, CLIENT_ERROR_API_KEY_INVALID

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_content_service_without_images(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test generate content service."""
    stubbed_generated_content = (
        "I'm thrilled to welcome you all to the release "
        "party for the latest version of Home Assistant!"
    )

    with patch(
        "google.genai.models.AsyncModels.generate_content",
        return_value=Mock(
            text=stubbed_generated_content,
            prompt_feedback=None,
            candidates=[Mock()],
        ),
    ) as mock_generate:
        response = await hass.services.async_call(
            "google_generative_ai_conversation",
            "generate_content",
            {"prompt": "Write an opening speech for a Home Assistant release party"},
            blocking=True,
            return_response=True,
        )

    assert response == {
        "text": stubbed_generated_content,
    }
    assert [tuple(mock_call) for mock_call in mock_generate.mock_calls] == snapshot


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_content_service_with_image(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test generate content service."""
    stubbed_generated_content = (
        "A mail carrier is at your front door delivering a package"
    )

    with (
        patch(
            "google.genai.models.AsyncModels.generate_content",
            return_value=Mock(
                text=stubbed_generated_content,
                prompt_feedback=None,
                candidates=[Mock()],
            ),
        ) as mock_generate,
        patch(
            "google.genai.files.Files.upload",
            side_effect=[
                File(name="doorbell_snapshot.jpg", state=FileState.ACTIVE),
                File(name="context.txt", state=FileState.ACTIVE),
            ],
        ),
        patch("pathlib.Path.exists", return_value=True),
        patch.object(hass.config, "is_allowed_path", return_value=True),
        patch("mimetypes.guess_type", return_value=["image/jpeg"]),
    ):
        response = await hass.services.async_call(
            "google_generative_ai_conversation",
            "generate_content",
            {
                "prompt": "Describe this image from my doorbell camera",
                "filenames": ["doorbell_snapshot.jpg", "context.txt"],
            },
            blocking=True,
            return_response=True,
        )

    assert response == {
        "text": stubbed_generated_content,
    }
    assert [tuple(mock_call) for mock_call in mock_generate.mock_calls] == snapshot


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_content_file_processing_succeeds(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test generate content service."""
    stubbed_generated_content = (
        "A mail carrier is at your front door delivering a package"
    )

    with (
        patch(
            "google.genai.models.AsyncModels.generate_content",
            return_value=Mock(
                text=stubbed_generated_content,
                prompt_feedback=None,
                candidates=[Mock()],
            ),
        ) as mock_generate,
        patch("pathlib.Path.exists", return_value=True),
        patch.object(hass.config, "is_allowed_path", return_value=True),
        patch("builtins.open", mock_open(read_data="this is an image")),
        patch("mimetypes.guess_type", return_value=["image/jpeg"]),
        patch(
            "google.genai.files.Files.upload",
            side_effect=[
                File(name="doorbell_snapshot.jpg", state=FileState.ACTIVE),
                File(name="context.txt", state=FileState.PROCESSING),
            ],
        ),
        patch(
            "google.genai.files.AsyncFiles.get",
            side_effect=[
                File(name="context.txt", state=FileState.PROCESSING),
                File(name="context.txt", state=FileState.ACTIVE),
            ],
        ),
    ):
        response = await hass.services.async_call(
            "google_generative_ai_conversation",
            "generate_content",
            {
                "prompt": "Describe this image from my doorbell camera",
                "filenames": ["doorbell_snapshot.jpg", "context.txt"],
            },
            blocking=True,
            return_response=True,
        )

    assert response == {
        "text": stubbed_generated_content,
    }
    assert [tuple(mock_call) for mock_call in mock_generate.mock_calls] == snapshot


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_content_file_processing_fails(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test generate content service."""
    stubbed_generated_content = (
        "A mail carrier is at your front door delivering a package"
    )

    with (
        patch(
            "google.genai.models.AsyncModels.generate_content",
            return_value=Mock(
                text=stubbed_generated_content,
                prompt_feedback=None,
                candidates=[Mock()],
            ),
        ),
        patch("pathlib.Path.exists", return_value=True),
        patch.object(hass.config, "is_allowed_path", return_value=True),
        patch("builtins.open", mock_open(read_data="this is an image")),
        patch("mimetypes.guess_type", return_value=["image/jpeg"]),
        patch(
            "google.genai.files.Files.upload",
            side_effect=[
                File(name="doorbell_snapshot.jpg", state=FileState.ACTIVE),
                File(name="context.txt", state=FileState.PROCESSING),
            ],
        ),
        patch(
            "google.genai.files.AsyncFiles.get",
            side_effect=[
                File(name="context.txt", state=FileState.PROCESSING),
                File(
                    name="context.txt",
                    state=FileState.FAILED,
                    error={"message": "File processing failed"},
                ),
            ],
        ),
        pytest.raises(
            HomeAssistantError,
            match="File `context.txt` processing failed, reason: File processing failed",
        ),
    ):
        await hass.services.async_call(
            "google_generative_ai_conversation",
            "generate_content",
            {
                "prompt": "Describe this image from my doorbell camera",
                "filenames": ["doorbell_snapshot.jpg", "context.txt"],
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_content_service_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test generate content service handles errors."""
    with (
        patch(
            "google.genai.models.AsyncModels.generate_content",
            side_effect=API_ERROR_500,
        ),
        pytest.raises(
            HomeAssistantError,
            match="Error generating content: 500 internal-error. {'message': 'Internal Server Error', 'status': 'internal-error'}",
        ),
    ):
        await hass.services.async_call(
            "google_generative_ai_conversation",
            "generate_content",
            {"prompt": "write a story about an epic fail"},
            blocking=True,
            return_response=True,
        )


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_content_response_has_empty_parts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test generate content service handles response with empty parts."""
    with (
        patch(
            "google.genai.models.AsyncModels.generate_content",
            return_value=Mock(
                prompt_feedback=None,
                candidates=[Mock(content=Mock(parts=[]))],
            ),
        ),
        pytest.raises(HomeAssistantError, match="Unknown error generating content"),
    ):
        await hass.services.async_call(
            "google_generative_ai_conversation",
            "generate_content",
            {"prompt": "write a story about an epic fail"},
            blocking=True,
            return_response=True,
        )


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_content_service_with_image_not_allowed_path(
    hass: HomeAssistant,
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
            "google_generative_ai_conversation",
            "generate_content",
            {
                "prompt": "Describe this image from my doorbell camera",
                "filenames": "doorbell_snapshot.jpg",
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_content_service_with_image_not_exists(
    hass: HomeAssistant,
) -> None:
    """Test generate content service with an image that does not exist."""
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch.object(hass.config, "is_allowed_path", return_value=True),
        patch("pathlib.Path.exists", return_value=False),
        pytest.raises(
            HomeAssistantError, match="`doorbell_snapshot.jpg` does not exist"
        ),
    ):
        await hass.services.async_call(
            "google_generative_ai_conversation",
            "generate_content",
            {
                "prompt": "Describe this image from my doorbell camera",
                "filenames": "doorbell_snapshot.jpg",
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize(
    ("side_effect", "state", "reauth"),
    [
        (
            API_ERROR_500,
            ConfigEntryState.SETUP_ERROR,
            False,
        ),
        (
            Timeout,
            ConfigEntryState.SETUP_RETRY,
            False,
        ),
        (
            CLIENT_ERROR_API_KEY_INVALID,
            ConfigEntryState.SETUP_ERROR,
            True,
        ),
    ],
)
async def test_config_entry_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, side_effect, state, reauth
) -> None:
    """Test different configuration entry errors."""
    mock_client = AsyncMock()
    mock_client.get_model.side_effect = side_effect
    with patch("google.genai.models.AsyncModels.get", side_effect=side_effect):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state == state
        assert any(mock_config_entry.async_get_active_flows(hass, {"reauth"})) == reauth


@pytest.mark.usefixtures("mock_init_component")
async def test_load_entry_with_unloaded_entries(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test loading an entry with unloaded entries."""
    config_entries = hass.config_entries.async_entries(
        "google_generative_ai_conversation"
    )
    runtime_data = config_entries[0].runtime_data
    await hass.config_entries.async_unload(config_entries[0].entry_id)

    entry = MockConfigEntry(
        domain="google_generative_ai_conversation",
        title="Google Generative AI Conversation",
        data={
            "api_key": "bla",
        },
        state=ConfigEntryState.LOADED,
    )
    entry.runtime_data = runtime_data
    entry.add_to_hass(hass)

    stubbed_generated_content = (
        "I'm thrilled to welcome you all to the release "
        "party for the latest version of Home Assistant!"
    )

    with patch(
        "google.genai.models.AsyncModels.generate_content",
        return_value=Mock(
            text=stubbed_generated_content,
            prompt_feedback=None,
            candidates=[Mock()],
        ),
    ) as mock_generate:
        response = await hass.services.async_call(
            "google_generative_ai_conversation",
            "generate_content",
            {"prompt": "Write an opening speech for a Home Assistant release party"},
            blocking=True,
            return_response=True,
        )

    assert response == {
        "text": stubbed_generated_content,
    }
    assert [tuple(mock_call) for mock_call in mock_generate.mock_calls] == snapshot


async def test_migration_from_v1(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration from version 1 to version 2."""
    # Create a v1 config entry with conversation options and an entity
    options = {
        "recommended": True,
        "llm_hass_api": ["assist"],
        "prompt": "You are a helpful assistant",
        "chat_model": "models/gemini-2.0-flash",
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "1234"},
        options=options,
        version=1,
        title="Google Generative AI",
    )
    mock_config_entry.add_to_hass(hass)
    mock_config_entry_2 = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "1234"},
        options=options,
        version=1,
        title="Google Generative AI 2",
    )
    mock_config_entry_2.add_to_hass(hass)

    device_1 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.entry_id)},
        name=mock_config_entry.title,
        manufacturer="Google",
        model="Generative AI",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry.entry_id,
        config_entry=mock_config_entry,
        device_id=device_1.id,
        suggested_object_id="google_generative_ai_conversation",
    )

    device_2 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry_2.entry_id,
        identifiers={(DOMAIN, mock_config_entry_2.entry_id)},
        name=mock_config_entry_2.title,
        manufacturer="Google",
        model="Generative AI",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry_2.entry_id,
        config_entry=mock_config_entry_2,
        device_id=device_2.id,
        suggested_object_id="google_generative_ai_conversation_2",
    )

    # Run migration
    with patch(
        "homeassistant.components.google_generative_ai_conversation.async_setup_entry",
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
    assert entry.title == DEFAULT_TITLE
    assert len(entry.subentries) == 5
    conversation_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "conversation"
    ]
    assert len(conversation_subentries) == 2
    for subentry in conversation_subentries:
        assert subentry.subentry_type == "conversation"
        assert subentry.data == options
        assert "Google Generative AI" in subentry.title
    tts_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "tts"
    ]
    assert len(tts_subentries) == 1
    assert tts_subentries[0].data == RECOMMENDED_TTS_OPTIONS
    assert tts_subentries[0].title == DEFAULT_TTS_NAME
    ai_task_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "ai_task_data"
    ]
    assert len(ai_task_subentries) == 1
    assert ai_task_subentries[0].data == RECOMMENDED_AI_TASK_OPTIONS
    assert ai_task_subentries[0].title == DEFAULT_AI_TASK_NAME
    stt_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "stt"
    ]
    assert len(stt_subentries) == 1
    assert stt_subentries[0].data == RECOMMENDED_STT_OPTIONS
    assert stt_subentries[0].title == DEFAULT_STT_NAME

    subentry = conversation_subentries[0]

    entity = entity_registry.async_get("conversation.google_generative_ai_conversation")
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

    entity = entity_registry.async_get(
        "conversation.google_generative_ai_conversation_2"
    )
    assert entity.unique_id == subentry.subentry_id
    assert entity.config_subentry_id == subentry.subentry_id
    assert entity.config_entry_id == entry.entry_id
    assert not device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry_2.entry_id)}
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
                    "conversation_entity_id": "conversation.google_generative_ai_conversation_2",
                    "device_disabled_by": None,
                    "entity_disabled_by": None,
                    "device": 1,
                },
                {
                    "conversation_entity_id": "conversation.google_generative_ai_conversation",
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
                    "conversation_entity_id": "conversation.google_generative_ai_conversation",
                    "device_disabled_by": None,
                    "entity_disabled_by": None,
                    "device": 0,
                },
                {
                    "conversation_entity_id": "conversation.google_generative_ai_conversation_2",
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
                    "conversation_entity_id": "conversation.google_generative_ai_conversation",
                    "device_disabled_by": DeviceEntryDisabler.CONFIG_ENTRY,
                    "entity_disabled_by": RegistryEntryDisabler.CONFIG_ENTRY,
                    "device": 0,
                },
                {
                    "conversation_entity_id": "conversation.google_generative_ai_conversation_2",
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
        "chat_model": "models/gemini-2.0-flash",
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "1234"},
        options=options,
        version=1,
        title="Google Generative AI",
        disabled_by=config_entry_disabled_by[0],
    )
    mock_config_entry.add_to_hass(hass)
    mock_config_entry_2 = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "1234"},
        options=options,
        version=1,
        title="Google Generative AI 2",
        disabled_by=config_entry_disabled_by[1],
    )
    mock_config_entry_2.add_to_hass(hass)
    mock_config_entries = [mock_config_entry, mock_config_entry_2]

    device_1 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.entry_id)},
        name=mock_config_entry.title,
        manufacturer="Google",
        model="Generative AI",
        entry_type=dr.DeviceEntryType.SERVICE,
        disabled_by=device_disabled_by[0],
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry.entry_id,
        config_entry=mock_config_entry,
        device_id=device_1.id,
        suggested_object_id="google_generative_ai_conversation",
        disabled_by=entity_disabled_by[0],
    )

    device_2 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry_2.entry_id,
        identifiers={(DOMAIN, mock_config_entry_2.entry_id)},
        name=mock_config_entry_2.title,
        manufacturer="Google",
        model="Generative AI",
        entry_type=dr.DeviceEntryType.SERVICE,
        disabled_by=device_disabled_by[1],
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry_2.entry_id,
        config_entry=mock_config_entry_2,
        device_id=device_2.id,
        suggested_object_id="google_generative_ai_conversation_2",
        disabled_by=entity_disabled_by[1],
    )

    devices = [device_1, device_2]

    # Run migration
    with patch(
        "homeassistant.components.google_generative_ai_conversation.async_setup_entry",
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
    assert entry.title == DEFAULT_TITLE
    assert len(entry.subentries) == 5
    conversation_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "conversation"
    ]
    assert len(conversation_subentries) == 2
    for subentry in conversation_subentries:
        assert subentry.subentry_type == "conversation"
        assert subentry.data == options
        assert "Google Generative AI" in subentry.title
    tts_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "tts"
    ]
    assert len(tts_subentries) == 1
    assert tts_subentries[0].data == RECOMMENDED_TTS_OPTIONS
    assert tts_subentries[0].title == DEFAULT_TTS_NAME
    ai_task_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "ai_task_data"
    ]
    assert len(ai_task_subentries) == 1
    assert ai_task_subentries[0].data == RECOMMENDED_AI_TASK_OPTIONS
    assert ai_task_subentries[0].title == DEFAULT_AI_TASK_NAME
    stt_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "stt"
    ]
    assert len(stt_subentries) == 1
    assert stt_subentries[0].data == RECOMMENDED_STT_OPTIONS
    assert stt_subentries[0].title == DEFAULT_STT_NAME

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


async def test_migration_from_v1_with_multiple_keys(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration from version 1 to version 2."""
    # Create a v1 config entry with conversation options and an entity
    options = {
        "recommended": True,
        "llm_hass_api": ["assist"],
        "prompt": "You are a helpful assistant",
        "chat_model": "models/gemini-2.0-flash",
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "1234"},
        options=options,
        version=1,
        title="Google Generative AI",
    )
    mock_config_entry.add_to_hass(hass)
    mock_config_entry_2 = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "12345"},
        options=options,
        version=1,
        title="Google Generative AI 2",
    )
    mock_config_entry_2.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.entry_id)},
        name=mock_config_entry.title,
        manufacturer="Google",
        model="Generative AI",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry.entry_id,
        config_entry=mock_config_entry,
        device_id=device.id,
        suggested_object_id="google_generative_ai_conversation",
    )

    device_2 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry_2.entry_id,
        identifiers={(DOMAIN, mock_config_entry_2.entry_id)},
        name=mock_config_entry_2.title,
        manufacturer="Google",
        model="Generative AI",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry_2.entry_id,
        config_entry=mock_config_entry_2,
        device_id=device_2.id,
        suggested_object_id="google_generative_ai_conversation_2",
    )

    # Run migration
    with patch(
        "homeassistant.components.google_generative_ai_conversation.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2

    for entry in entries:
        assert entry.version == 2
        assert entry.minor_version == 4
        assert not entry.options
        assert entry.title == DEFAULT_TITLE
        assert len(entry.subentries) == 4
        subentry = list(entry.subentries.values())[0]
        assert subentry.subentry_type == "conversation"
        assert subentry.data == options
        assert "Google Generative AI" in subentry.title
        subentry = list(entry.subentries.values())[1]
        assert subentry.subentry_type == "tts"
        assert subentry.data == RECOMMENDED_TTS_OPTIONS
        assert subentry.title == DEFAULT_TTS_NAME
        subentry = list(entry.subentries.values())[2]
        assert subentry.subentry_type == "ai_task_data"
        assert subentry.data == RECOMMENDED_AI_TASK_OPTIONS
        assert subentry.title == DEFAULT_AI_TASK_NAME
        subentry = list(entry.subentries.values())[3]
        assert subentry.subentry_type == "stt"
        assert subentry.data == RECOMMENDED_STT_OPTIONS
        assert subentry.title == DEFAULT_STT_NAME

        dev = device_registry.async_get_device(
            identifiers={(DOMAIN, list(entry.subentries.values())[0].subentry_id)}
        )
        assert dev is not None
        assert dev.config_entries == {entry.entry_id}
        assert dev.config_entries_subentries == {
            entry.entry_id: {list(entry.subentries.values())[0].subentry_id}
        }


async def test_migration_from_v1_with_same_keys(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration from version 1 to version 2 with same API keys."""
    # Create v1 config entries with the same API key
    options = {
        "recommended": True,
        "llm_hass_api": ["assist"],
        "prompt": "You are a helpful assistant",
        "chat_model": "models/gemini-2.0-flash",
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "1234"},
        options=options,
        version=1,
        title="Google Generative AI",
    )
    mock_config_entry.add_to_hass(hass)
    mock_config_entry_2 = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "1234"},
        options=options,
        version=1,
        title="Google Generative AI 2",
    )
    mock_config_entry_2.add_to_hass(hass)

    device_1 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.entry_id)},
        name=mock_config_entry.title,
        manufacturer="Google",
        model="Generative AI",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry.entry_id,
        config_entry=mock_config_entry,
        device_id=device_1.id,
        suggested_object_id="google_generative_ai_conversation",
    )

    device_2 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry_2.entry_id,
        identifiers={(DOMAIN, mock_config_entry_2.entry_id)},
        name=mock_config_entry_2.title,
        manufacturer="Google",
        model="Generative AI",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry_2.entry_id,
        config_entry=mock_config_entry_2,
        device_id=device_2.id,
        suggested_object_id="google_generative_ai_conversation_2",
    )

    # Run migration
    with patch(
        "homeassistant.components.google_generative_ai_conversation.async_setup_entry",
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
    assert entry.title == DEFAULT_TITLE
    assert len(entry.subentries) == 5
    conversation_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "conversation"
    ]
    assert len(conversation_subentries) == 2
    for subentry in conversation_subentries:
        assert subentry.subentry_type == "conversation"
        assert subentry.data == options
        assert "Google Generative AI" in subentry.title
    tts_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "tts"
    ]
    assert len(tts_subentries) == 1
    assert tts_subentries[0].data == RECOMMENDED_TTS_OPTIONS
    assert tts_subentries[0].title == DEFAULT_TTS_NAME
    ai_task_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "ai_task_data"
    ]
    assert len(ai_task_subentries) == 1
    assert ai_task_subentries[0].data == RECOMMENDED_AI_TASK_OPTIONS
    assert ai_task_subentries[0].title == DEFAULT_AI_TASK_NAME
    stt_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "stt"
    ]
    assert len(stt_subentries) == 1
    assert stt_subentries[0].data == RECOMMENDED_STT_OPTIONS
    assert stt_subentries[0].title == DEFAULT_STT_NAME

    subentry = conversation_subentries[0]

    entity = entity_registry.async_get("conversation.google_generative_ai_conversation")
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

    entity = entity_registry.async_get(
        "conversation.google_generative_ai_conversation_2"
    )
    assert entity.unique_id == subentry.subentry_id
    assert entity.config_subentry_id == subentry.subentry_id
    assert entity.config_entry_id == entry.entry_id
    assert not device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry_2.entry_id)}
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
    ("device_changes", "extra_subentries", "expected_device_subentries"),
    [
        # Scenario where we have a v2.1 config entry migrated by HA Core 2025.7.0b0:
        # Wrong device registry, no TTS subentry
        (
            {"add_config_entry_id": "mock_entry_id", "add_config_subentry_id": None},
            [],
            {"mock_entry_id": {None, "mock_id_1"}},
        ),
        # Scenario where we have a v2.1 config entry migrated by HA Core 2025.7.0b1:
        # Wrong device registry, TTS subentry created
        (
            {"add_config_entry_id": "mock_entry_id", "add_config_subentry_id": None},
            [
                ConfigSubentryData(
                    data=RECOMMENDED_TTS_OPTIONS,
                    subentry_id="mock_id_3",
                    subentry_type="tts",
                    title=DEFAULT_TTS_NAME,
                    unique_id=None,
                )
            ],
            {"mock_entry_id": {None, "mock_id_1"}},
        ),
        # Scenario where we have a v2.1 config entry migrated by HA Core 2025.7.0b2
        # or later: Correct device registry, TTS subentry created
        (
            {},
            [
                ConfigSubentryData(
                    data=RECOMMENDED_TTS_OPTIONS,
                    subentry_id="mock_id_3",
                    subentry_type="tts",
                    title=DEFAULT_TTS_NAME,
                    unique_id=None,
                )
            ],
            {"mock_entry_id": {"mock_id_1"}},
        ),
    ],
)
async def test_migration_from_v2_1(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    device_changes: dict[str, str],
    extra_subentries: list[ConfigSubentryData],
    expected_device_subentries: dict[str, set[str | None]],
) -> None:
    """Test migration from version 2.1.

    This tests we clean up the broken migration in Home Assistant Core
    2025.7.0b0-2025.7.0b1 and add AI Task and STT subentries:
    - Fix device registry (Fixed in Home Assistant Core 2025.7.0b2)
    - Add TTS subentry (Added in Home Assistant Core 2025.7.0b1)
    - Add AI Task subentry (Added in version 2.3)
    - Add STT subentry (Added in version 2.3)
    """
    # Create a v2.1 config entry with 2 subentries, devices and entities
    options = {
        "recommended": True,
        "llm_hass_api": ["assist"],
        "prompt": "You are a helpful assistant",
        "chat_model": "models/gemini-2.0-flash",
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "1234"},
        entry_id="mock_entry_id",
        version=2,
        minor_version=1,
        subentries_data=[
            ConfigSubentryData(
                data=options,
                subentry_id="mock_id_1",
                subentry_type="conversation",
                title="Google Generative AI",
                unique_id=None,
            ),
            ConfigSubentryData(
                data=options,
                subentry_id="mock_id_2",
                subentry_type="conversation",
                title="Google Generative AI 2",
                unique_id=None,
            ),
            *extra_subentries,
        ],
        title="Google Generative AI",
    )
    mock_config_entry.add_to_hass(hass)

    device_1 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        config_subentry_id="mock_id_1",
        identifiers={(DOMAIN, "mock_id_1")},
        name="Google Generative AI",
        manufacturer="Google",
        model="Generative AI",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    device_1 = device_registry.async_update_device(device_1.id, **device_changes)
    assert device_1.config_entries_subentries == expected_device_subentries
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        "mock_id_1",
        config_entry=mock_config_entry,
        config_subentry_id="mock_id_1",
        device_id=device_1.id,
        suggested_object_id="google_generative_ai_conversation",
    )

    device_2 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        config_subentry_id="mock_id_2",
        identifiers={(DOMAIN, "mock_id_2")},
        name="Google Generative AI 2",
        manufacturer="Google",
        model="Generative AI",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        "mock_id_2",
        config_entry=mock_config_entry,
        config_subentry_id="mock_id_2",
        device_id=device_2.id,
        suggested_object_id="google_generative_ai_conversation_2",
    )

    # Run migration
    with patch(
        "homeassistant.components.google_generative_ai_conversation.async_setup_entry",
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
    assert entry.title == DEFAULT_TITLE
    assert len(entry.subentries) == 5
    conversation_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "conversation"
    ]
    assert len(conversation_subentries) == 2
    for subentry in conversation_subentries:
        assert subentry.subentry_type == "conversation"
        assert subentry.data == options
        assert "Google Generative AI" in subentry.title
    tts_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "tts"
    ]
    assert len(tts_subentries) == 1
    assert tts_subentries[0].data == RECOMMENDED_TTS_OPTIONS
    assert tts_subentries[0].title == DEFAULT_TTS_NAME
    ai_task_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "ai_task_data"
    ]
    assert len(ai_task_subentries) == 1
    assert ai_task_subentries[0].data == RECOMMENDED_AI_TASK_OPTIONS
    assert ai_task_subentries[0].title == DEFAULT_AI_TASK_NAME
    stt_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "stt"
    ]
    assert len(stt_subentries) == 1
    assert stt_subentries[0].data == RECOMMENDED_STT_OPTIONS
    assert stt_subentries[0].title == DEFAULT_STT_NAME

    subentry = conversation_subentries[0]

    entity = entity_registry.async_get("conversation.google_generative_ai_conversation")
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

    entity = entity_registry.async_get(
        "conversation.google_generative_ai_conversation_2"
    )
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


async def test_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Assert that devices are created correctly."""
    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert devices == snapshot


async def test_migrate_entry_from_v2_2(hass: HomeAssistant) -> None:
    """Test migration from version 2.2."""
    # Create a v2.2 config entry with conversation and TTS subentries
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-api-key"},
        version=2,
        minor_version=2,
        subentries_data=[
            {
                "data": RECOMMENDED_CONVERSATION_OPTIONS,
                "subentry_type": "conversation",
                "title": DEFAULT_CONVERSATION_NAME,
                "unique_id": None,
            },
            {
                "data": RECOMMENDED_TTS_OPTIONS,
                "subentry_type": "tts",
                "title": DEFAULT_TTS_NAME,
                "unique_id": None,
            },
        ],
    )
    mock_config_entry.add_to_hass(hass)

    # Verify initial state
    assert mock_config_entry.version == 2
    assert mock_config_entry.minor_version == 2
    assert len(mock_config_entry.subentries) == 2

    # Run setup to trigger migration
    with patch(
        "homeassistant.components.google_generative_ai_conversation.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        assert result is True
        await hass.async_block_till_done()

    # Verify migration completed
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]

    # Check version and subversion were updated
    assert entry.version == 2
    assert entry.minor_version == 4

    # Check we now have conversation, tts, stt, and ai_task_data subentries
    assert len(entry.subentries) == 4

    subentries = {
        subentry.subentry_type: subentry for subentry in entry.subentries.values()
    }
    assert "conversation" in subentries
    assert "tts" in subentries
    assert "ai_task_data" in subentries

    # Find and verify the ai_task_data subentry
    ai_task_subentry = subentries["ai_task_data"]
    assert ai_task_subentry is not None
    assert ai_task_subentry.title == DEFAULT_AI_TASK_NAME
    assert ai_task_subentry.data == RECOMMENDED_AI_TASK_OPTIONS

    # Find and verify the stt subentry
    ai_task_subentry = subentries["stt"]
    assert ai_task_subentry is not None
    assert ai_task_subentry.title == DEFAULT_STT_NAME
    assert ai_task_subentry.data == RECOMMENDED_STT_OPTIONS

    # Verify conversation subentry is still there and unchanged
    conversation_subentry = subentries["conversation"]
    assert conversation_subentry is not None
    assert conversation_subentry.title == DEFAULT_CONVERSATION_NAME
    assert conversation_subentry.data == RECOMMENDED_CONVERSATION_OPTIONS

    # Verify TTS subentry is still there and unchanged
    tts_subentry = subentries["tts"]
    assert tts_subentry is not None
    assert tts_subentry.title == DEFAULT_TTS_NAME
    assert tts_subentry.data == RECOMMENDED_TTS_OPTIONS


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
    # Create a v2.3 config entry with conversation and TTS subentries
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
            {
                "data": RECOMMENDED_TTS_OPTIONS,
                "subentry_type": "tts",
                "title": DEFAULT_TTS_NAME,
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
        manufacturer="Google",
        model="Generative AI",
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
        suggested_object_id="google_generative_ai_conversation",
    )

    # Verify initial state
    assert mock_config_entry.version == 2
    assert mock_config_entry.minor_version == 3
    assert len(mock_config_entry.subentries) == 2
    assert mock_config_entry.disabled_by == config_entry_disabled_by
    assert conversation_device.disabled_by == device_disabled_by
    assert conversation_entity.disabled_by == entity_disabled_by

    # Run setup to trigger migration
    with patch(
        "homeassistant.components.google_generative_ai_conversation.async_setup_entry",
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
