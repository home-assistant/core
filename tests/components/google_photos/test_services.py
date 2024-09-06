"""Tests for Google Photos."""

from unittest.mock import Mock, patch

from google_photos_library_api.exceptions import GooglePhotosApiError
from google_photos_library_api.model import (
    CreateMediaItemsResult,
    MediaItem,
    NewMediaItemResult,
    Status,
)
import pytest

from homeassistant.components.google_photos.const import DOMAIN, READ_SCOPES
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("setup_integration")
async def test_upload_service(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api: Mock,
) -> None:
    """Test service call to upload content."""
    assert hass.services.has_service(DOMAIN, "upload")

    mock_api.create_media_items.return_value = CreateMediaItemsResult(
        new_media_item_results=[
            NewMediaItemResult(
                upload_token="some-upload-token",
                status=Status(code=200),
                media_item=MediaItem(id="new-media-item-id-1"),
            )
        ]
    )

    with (
        patch(
            "homeassistant.components.google_photos.services.Path.read_bytes",
            return_value=b"image bytes",
        ),
        patch(
            "homeassistant.components.google_photos.services.Path.exists",
            return_value=True,
        ),
        patch.object(hass.config, "is_allowed_path", return_value=True),
    ):
        response = await hass.services.async_call(
            DOMAIN,
            "upload",
            {
                "config_entry_id": config_entry.entry_id,
                "filename": "doorbell_snapshot.jpg",
            },
            blocking=True,
            return_response=True,
        )

    assert response == {"media_items": [{"media_item_id": "new-media-item-id-1"}]}


@pytest.mark.usefixtures("setup_integration")
async def test_upload_service_config_entry_not_found(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test upload service call with a config entry that does not exist."""
    with pytest.raises(HomeAssistantError, match="not found in registry"):
        await hass.services.async_call(
            DOMAIN,
            "upload",
            {
                "config_entry_id": "invalid-config-entry-id",
                "filename": "doorbell_snapshot.jpg",
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.usefixtures("setup_integration")
async def test_config_entry_not_loaded(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test upload service call with a config entry that is not loaded."""
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED

    with pytest.raises(HomeAssistantError, match="not found in registry"):
        await hass.services.async_call(
            DOMAIN,
            "upload",
            {
                "config_entry_id": config_entry.unique_id,
                "filename": "doorbell_snapshot.jpg",
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.usefixtures("setup_integration")
async def test_path_is_not_allowed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test upload service call with a filename path that is not allowed."""
    with (
        patch.object(hass.config, "is_allowed_path", return_value=False),
        pytest.raises(HomeAssistantError, match="no access to path"),
    ):
        await hass.services.async_call(
            DOMAIN,
            "upload",
            {
                "config_entry_id": config_entry.entry_id,
                "filename": "doorbell_snapshot.jpg",
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.usefixtures("setup_integration")
async def test_filename_does_not_exist(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test upload service call with a filename path that does not exist."""
    with (
        patch.object(hass.config, "is_allowed_path", return_value=True),
        patch("pathlib.Path.exists", return_value=False),
        pytest.raises(HomeAssistantError, match="does not exist"),
    ):
        await hass.services.async_call(
            DOMAIN,
            "upload",
            {
                "config_entry_id": config_entry.entry_id,
                "filename": "doorbell_snapshot.jpg",
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.usefixtures("setup_integration")
async def test_upload_service_upload_content_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api: Mock,
) -> None:
    """Test service call to upload content."""

    mock_api.upload_content.side_effect = GooglePhotosApiError()

    with (
        patch(
            "homeassistant.components.google_photos.services.Path.read_bytes",
            return_value=b"image bytes",
        ),
        patch(
            "homeassistant.components.google_photos.services.Path.exists",
            return_value=True,
        ),
        patch.object(hass.config, "is_allowed_path", return_value=True),
        pytest.raises(HomeAssistantError, match="Failed to upload content"),
    ):
        await hass.services.async_call(
            DOMAIN,
            "upload",
            {
                "config_entry_id": config_entry.entry_id,
                "filename": "doorbell_snapshot.jpg",
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.usefixtures("setup_integration")
async def test_upload_service_fails_create(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api: Mock,
) -> None:
    """Test service call to upload content."""

    mock_api.create_media_items.side_effect = GooglePhotosApiError()

    with (
        patch(
            "homeassistant.components.google_photos.services.Path.read_bytes",
            return_value=b"image bytes",
        ),
        patch(
            "homeassistant.components.google_photos.services.Path.exists",
            return_value=True,
        ),
        patch.object(hass.config, "is_allowed_path", return_value=True),
        pytest.raises(
            HomeAssistantError, match="Google Photos API responded with error"
        ),
    ):
        await hass.services.async_call(
            DOMAIN,
            "upload",
            {
                "config_entry_id": config_entry.entry_id,
                "filename": "doorbell_snapshot.jpg",
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(
    ("scopes"),
    [
        READ_SCOPES,
    ],
)
async def test_upload_service_no_scope(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test service call to upload content but the config entry is read-only."""

    with pytest.raises(HomeAssistantError, match="not granted permission"):
        await hass.services.async_call(
            DOMAIN,
            "upload",
            {
                "config_entry_id": config_entry.entry_id,
                "filename": "doorbell_snapshot.jpg",
            },
            blocking=True,
            return_response=True,
        )
