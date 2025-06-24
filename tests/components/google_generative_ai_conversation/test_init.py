"""Tests for the Google Generative AI Conversation integration."""

from unittest.mock import AsyncMock, Mock, mock_open, patch

from google.genai.types import File, FileState
import pytest
from requests.exceptions import Timeout
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.google_generative_ai_conversation.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

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
            return_value=b"some file",
        ),
        patch("pathlib.Path.exists", return_value=True),
        patch.object(hass.config, "is_allowed_path", return_value=True),
        patch("builtins.open", mock_open(read_data="this is an image")),
        patch("mimetypes.guess_type", return_value=["image/jpeg"]),
    ):
        response = await hass.services.async_call(
            "google_generative_ai_conversation",
            "generate_content",
            {
                "prompt": "Describe this image from my doorbell camera",
                "filenames": ["doorbell_snapshot.jpg", "context.txt", "context.txt"],
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
                "filenames": ["doorbell_snapshot.jpg", "context.txt", "context.txt"],
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
                "filenames": ["doorbell_snapshot.jpg", "context.txt", "context.txt"],
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


async def test_migration_from_v1_to_v2(
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
    assert not entry.options
    assert len(entry.subentries) == 2
    for subentry in entry.subentries.values():
        assert subentry.subentry_type == "conversation"
        assert subentry.data == options
        assert "Google Generative AI" in subentry.title

    subentry = list(entry.subentries.values())[0]

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

    subentry = list(entry.subentries.values())[1]

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


async def test_migration_from_v1_to_v2_with_multiple_keys(
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
        assert not entry.options
        assert len(entry.subentries) == 1
        subentry = list(entry.subentries.values())[0]
        assert subentry.subentry_type == "conversation"
        assert subentry.data == options
        assert "Google Generative AI" in subentry.title

        dev = device_registry.async_get_device(
            identifiers={(DOMAIN, list(entry.subentries.values())[0].subentry_id)}
        )
        assert dev is not None


async def test_migration_from_v1_to_v2_with_same_keys(
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
    assert not entry.options
    assert len(entry.subentries) == 2
    for subentry in entry.subentries.values():
        assert subentry.subentry_type == "conversation"
        assert subentry.data == options
        assert "Google Generative AI" in subentry.title

    subentry = list(entry.subentries.values())[0]

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

    subentry = list(entry.subentries.values())[1]

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
