"""Tests for Google Photos."""

from collections.abc import Generator
from dataclasses import dataclass
import re
from unittest.mock import Mock, patch

from google_photos_library_api.exceptions import GooglePhotosApiError
from google_photos_library_api.model import (
    Album,
    CreateMediaItemsResult,
    MediaItem,
    NewMediaItemResult,
    Status,
)
import pytest

from homeassistant.components.google_photos.const import DOMAIN, READ_SCOPE
from homeassistant.components.google_photos.services import (
    CONF_ALBUM,
    CONF_CONFIG_ENTRY_ID,
    UPLOAD_SERVICE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_FILENAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry

TEST_FILENAME = "doorbell_snapshot.jpg"
ALBUM_TITLE = "Album title"


@dataclass
class MockUploadFile:
    """Dataclass used to configure the test with a fake file behavior."""

    content: bytes = b"image bytes"
    exists: bool = True
    is_allowed_path: bool = True
    size: int | None = None


@pytest.fixture(name="upload_file")
def upload_file_fixture() -> None:
    """Fixture to set up test configuration with a fake file."""
    return MockUploadFile()


@pytest.fixture(autouse=True)
def mock_upload_file(
    hass: HomeAssistant, upload_file: MockUploadFile
) -> Generator[None]:
    """Fixture that mocks out the file calls using the FakeFile fixture."""
    with (
        patch(
            "homeassistant.components.google_photos.services.Path.read_bytes",
            return_value=upload_file.content,
        ),
        patch(
            "homeassistant.components.google_photos.services.Path.exists",
            return_value=upload_file.exists,
        ),
        patch.object(
            hass.config, "is_allowed_path", return_value=upload_file.is_allowed_path
        ),
        patch("pathlib.Path.stat") as mock_stat,
    ):
        mock_stat.return_value = Mock()
        mock_stat.return_value.st_size = (
            upload_file.size if upload_file.size else len(upload_file.content)
        )
        yield


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

    response = await hass.services.async_call(
        DOMAIN,
        UPLOAD_SERVICE,
        {
            CONF_CONFIG_ENTRY_ID: config_entry.entry_id,
            CONF_FILENAME: TEST_FILENAME,
            CONF_ALBUM: ALBUM_TITLE,
        },
        blocking=True,
        return_response=True,
    )

    assert response == {
        "media_items": [{"media_item_id": "new-media-item-id-1"}],
        "album_id": "album-media-id-1",
    }


@pytest.mark.usefixtures("setup_integration")
async def test_upload_service_config_entry_not_found(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test upload service call with a config entry that does not exist."""
    with pytest.raises(HomeAssistantError, match="not found in registry"):
        await hass.services.async_call(
            DOMAIN,
            UPLOAD_SERVICE,
            {
                CONF_CONFIG_ENTRY_ID: "invalid-config-entry-id",
                CONF_FILENAME: TEST_FILENAME,
                CONF_ALBUM: ALBUM_TITLE,
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
            UPLOAD_SERVICE,
            {
                CONF_CONFIG_ENTRY_ID: config_entry.unique_id,
                CONF_FILENAME: TEST_FILENAME,
                CONF_ALBUM: ALBUM_TITLE,
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize("upload_file", [MockUploadFile(is_allowed_path=False)])
async def test_path_is_not_allowed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test upload service call with a filename path that is not allowed."""
    with (
        pytest.raises(HomeAssistantError, match="no access to path"),
    ):
        await hass.services.async_call(
            DOMAIN,
            UPLOAD_SERVICE,
            {
                CONF_CONFIG_ENTRY_ID: config_entry.entry_id,
                CONF_FILENAME: TEST_FILENAME,
                CONF_ALBUM: ALBUM_TITLE,
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize("upload_file", [MockUploadFile(exists=False)])
async def test_filename_does_not_exist(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test upload service call with a filename path that does not exist."""
    with pytest.raises(HomeAssistantError, match="does not exist"):
        await hass.services.async_call(
            DOMAIN,
            UPLOAD_SERVICE,
            {
                CONF_CONFIG_ENTRY_ID: config_entry.entry_id,
                CONF_FILENAME: TEST_FILENAME,
                CONF_ALBUM: ALBUM_TITLE,
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

    with pytest.raises(HomeAssistantError, match="Failed to upload content"):
        await hass.services.async_call(
            DOMAIN,
            UPLOAD_SERVICE,
            {
                CONF_CONFIG_ENTRY_ID: config_entry.entry_id,
                CONF_FILENAME: TEST_FILENAME,
                CONF_ALBUM: ALBUM_TITLE,
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

    with pytest.raises(
        HomeAssistantError, match="Google Photos API responded with error"
    ):
        await hass.services.async_call(
            DOMAIN,
            UPLOAD_SERVICE,
            {
                CONF_CONFIG_ENTRY_ID: config_entry.entry_id,
                CONF_FILENAME: TEST_FILENAME,
                CONF_ALBUM: ALBUM_TITLE,
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(
    ("scopes"),
    [
        [READ_SCOPE],
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
            UPLOAD_SERVICE,
            {
                CONF_CONFIG_ENTRY_ID: config_entry.entry_id,
                CONF_FILENAME: TEST_FILENAME,
                CONF_ALBUM: ALBUM_TITLE,
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize("upload_file", [MockUploadFile(size=26 * 1024 * 1024)])
async def test_upload_size_limit(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test upload service call with a filename path that does not exist."""
    with pytest.raises(
        HomeAssistantError,
        match=re.escape(f"`{TEST_FILENAME}` is too large (27262976 > 20971520)"),
    ):
        await hass.services.async_call(
            DOMAIN,
            UPLOAD_SERVICE,
            {
                CONF_CONFIG_ENTRY_ID: config_entry.entry_id,
                CONF_FILENAME: TEST_FILENAME,
                CONF_ALBUM: ALBUM_TITLE,
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.usefixtures("setup_integration")
async def test_upload_to_new_album(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api: Mock,
) -> None:
    """Test service call to upload content to a new album."""
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
    mock_api.create_album.return_value = Album(id="album-media-id-2", title="New Album")
    response = await hass.services.async_call(
        DOMAIN,
        UPLOAD_SERVICE,
        {
            CONF_CONFIG_ENTRY_ID: config_entry.entry_id,
            CONF_FILENAME: TEST_FILENAME,
            CONF_ALBUM: "New Album",
        },
        blocking=True,
        return_response=True,
    )

    # Verify media item was created with the new album id
    mock_api.create_album.assert_awaited()
    assert response == {
        "media_items": [{"media_item_id": "new-media-item-id-1"}],
        "album_id": "album-media-id-2",
    }

    # Upload an additional item to the same album and assert that no new album is created
    mock_api.create_album.reset_mock()
    mock_api.create_media_items.reset_mock()
    mock_api.create_media_items.return_value = CreateMediaItemsResult(
        new_media_item_results=[
            NewMediaItemResult(
                upload_token="some-upload-token",
                status=Status(code=200),
                media_item=MediaItem(id="new-media-item-id-3"),
            )
        ]
    )
    response = await hass.services.async_call(
        DOMAIN,
        UPLOAD_SERVICE,
        {
            CONF_CONFIG_ENTRY_ID: config_entry.entry_id,
            CONF_FILENAME: TEST_FILENAME,
            CONF_ALBUM: "New Album",
        },
        blocking=True,
        return_response=True,
    )

    # Verify the album created last time is used
    mock_api.create_album.assert_not_awaited()
    assert response == {
        "media_items": [{"media_item_id": "new-media-item-id-3"}],
        "album_id": "album-media-id-2",
    }


@pytest.mark.usefixtures("setup_integration")
async def test_create_album_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api: Mock,
) -> None:
    """Test service call to upload content to a new album but creating the album fails."""
    assert hass.services.has_service(DOMAIN, "upload")

    mock_api.create_album.side_effect = GooglePhotosApiError()

    with pytest.raises(HomeAssistantError, match="Failed to create album"):
        await hass.services.async_call(
            DOMAIN,
            UPLOAD_SERVICE,
            {
                CONF_CONFIG_ENTRY_ID: config_entry.entry_id,
                CONF_FILENAME: TEST_FILENAME,
                CONF_ALBUM: "New Album",
            },
            blocking=True,
            return_response=True,
        )
