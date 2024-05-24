"""Tests for the Google Generative AI Conversation integration."""

from unittest.mock import AsyncMock, MagicMock, patch

from google.api_core.exceptions import ClientError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


async def test_generate_content_service_without_images(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generate content service."""
    stubbed_generated_content = (
        "I'm thrilled to welcome you all to the release "
        "party for the latest version of Home Assistant!"
    )

    with patch("google.generativeai.GenerativeModel") as mock_model:
        mock_response = MagicMock()
        mock_response.text = stubbed_generated_content
        mock_model.return_value.generate_content_async = AsyncMock(
            return_value=mock_response
        )
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
    assert [tuple(mock_call) for mock_call in mock_model.mock_calls] == snapshot


async def test_generate_content_service_with_image(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generate content service."""
    stubbed_generated_content = (
        "A mail carrier is at your front door delivering a package"
    )

    with (
        patch("google.generativeai.GenerativeModel") as mock_model,
        patch(
            "homeassistant.components.google_generative_ai_conversation.Path.read_bytes",
            return_value=b"image bytes",
        ),
        patch("pathlib.Path.exists", return_value=True),
        patch.object(hass.config, "is_allowed_path", return_value=True),
    ):
        mock_response = MagicMock()
        mock_response.text = stubbed_generated_content
        mock_model.return_value.generate_content_async = AsyncMock(
            return_value=mock_response
        )
        response = await hass.services.async_call(
            "google_generative_ai_conversation",
            "generate_content",
            {
                "prompt": "Describe this image from my doorbell camera",
                "image_filename": "doorbell_snapshot.jpg",
            },
            blocking=True,
            return_response=True,
        )

    assert response == {
        "text": stubbed_generated_content,
    }
    assert [tuple(mock_call) for mock_call in mock_model.mock_calls] == snapshot


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_content_service_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test generate content service handles errors."""
    with (
        patch("google.generativeai.GenerativeModel") as mock_model,
        pytest.raises(
            HomeAssistantError, match="Error generating content: None reason"
        ),
    ):
        mock_model.return_value.generate_content_async = AsyncMock(
            side_effect=ClientError("reason")
        )
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
        patch("google.generativeai.GenerativeModel") as mock_model,
        pytest.raises(HomeAssistantError, match="Error generating content"),
    ):
        mock_response = MagicMock()
        mock_response.parts = []
        mock_model.return_value.generate_content_async = AsyncMock(
            return_value=mock_response
        )
        await hass.services.async_call(
            "google_generative_ai_conversation",
            "generate_content",
            {"prompt": "write a story about an epic fail"},
            blocking=True,
            return_response=True,
        )


async def test_generate_content_service_with_image_not_allowed_path(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    snapshot: SnapshotAssertion,
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
                "image_filename": "doorbell_snapshot.jpg",
            },
            blocking=True,
            return_response=True,
        )


async def test_generate_content_service_with_image_not_exists(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    snapshot: SnapshotAssertion,
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
                "image_filename": "doorbell_snapshot.jpg",
            },
            blocking=True,
            return_response=True,
        )


async def test_generate_content_service_with_non_image(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generate content service with a non image."""
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch.object(hass.config, "is_allowed_path", return_value=True),
        patch("pathlib.Path.exists", return_value=True),
        pytest.raises(
            HomeAssistantError, match="`doorbell_snapshot.mp4` is not an image"
        ),
    ):
        await hass.services.async_call(
            "google_generative_ai_conversation",
            "generate_content",
            {
                "prompt": "Describe this image from my doorbell camera",
                "image_filename": "doorbell_snapshot.mp4",
            },
            blocking=True,
            return_response=True,
        )
