"""Tests for Google Photos."""

import http
from unittest.mock import Mock, patch

from googleapiclient.errors import HttpError
from httplib2 import Response
import pytest

from homeassistant.components.google_photos.api import UPLOAD_API
from homeassistant.components.google_photos.const import DOMAIN, READ_SCOPES
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.usefixtures("setup_integration")
async def test_upload_service(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    setup_api: Mock,
) -> None:
    """Test service call to upload content."""
    assert hass.services.has_service(DOMAIN, "upload")

    aioclient_mock.post(UPLOAD_API, text="some-upload-token")
    setup_api.return_value.mediaItems.return_value.batchCreate.return_value.execute.return_value = {
        "newMediaItemResults": [
            {
                "status": {
                    "code": 200,
                },
                "mediaItem": {
                    "id": "new-media-item-id-1",
                },
            }
        ]
    }

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
    aioclient_mock: AiohttpClientMocker,
    setup_api: Mock,
) -> None:
    """Test service call to upload content."""

    aioclient_mock.post(UPLOAD_API, status=http.HTTPStatus.SERVICE_UNAVAILABLE)

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
    aioclient_mock: AiohttpClientMocker,
    setup_api: Mock,
) -> None:
    """Test service call to upload content."""

    aioclient_mock.post(UPLOAD_API, text="some-upload-token")
    setup_api.return_value.mediaItems.return_value.batchCreate.return_value.execute.side_effect = HttpError(
        Response({"status": "403"}), b""
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
    aioclient_mock: AiohttpClientMocker,
    setup_api: Mock,
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
