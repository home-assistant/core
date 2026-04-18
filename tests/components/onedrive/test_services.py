"""Tests for OneDrive services."""

from collections.abc import Generator
from dataclasses import dataclass
import re
from typing import Any, cast
from unittest.mock import MagicMock, Mock, patch

from onedrive_personal_sdk.exceptions import OneDriveException
import pytest
import voluptuous as vol

from homeassistant.components.onedrive.const import DOMAIN
from homeassistant.components.onedrive.services import (
    CONF_CONFIG_ENTRY_ID,
    CONF_DESTINATION_FOLDER,
    CONF_DESTINATION_PATH,
    DELETE_SERVICE,
    UPLOAD_SERVICE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_FILENAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import setup_integration

from tests.common import MockConfigEntry

TEST_FILENAME = "doorbell_snapshot.jpg"
TEST_DESTINATION_PATH = "photos/snapshots/image.jpg"
DESINATION_FOLDER = "TestFolder"


@dataclass
class MockUploadFile:
    """Dataclass used to configure the test with a fake file behavior."""

    content: bytes = b"image bytes"
    exists: bool = True
    is_allowed_path: bool = True
    size: int | None = None


@pytest.fixture(name="upload_file")
def upload_file_fixture() -> MockUploadFile:
    """Fixture to set up test configuration with a fake file."""
    return MockUploadFile()


@pytest.fixture(autouse=True)
def mock_upload_file(
    hass: HomeAssistant, upload_file: MockUploadFile
) -> Generator[None]:
    """Fixture that mocks out the file calls using the FakeFile fixture."""
    with (
        patch(
            "homeassistant.components.onedrive.services.Path.read_bytes",
            return_value=upload_file.content,
        ),
        patch(
            "homeassistant.components.onedrive.services.Path.exists",
            return_value=upload_file.exists,
        ),
        patch.object(
            hass.config, "is_allowed_path", return_value=upload_file.is_allowed_path
        ),
        patch("pathlib.Path.stat") as mock_stat,
    ):
        mock_stat.return_value = Mock()
        mock_stat.return_value.st_size = upload_file.size or len(upload_file.content)
        yield


async def test_upload_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test service call to upload content."""
    await setup_integration(hass, mock_config_entry)

    assert hass.services.has_service(DOMAIN, "upload")

    response = await hass.services.async_call(
        DOMAIN,
        UPLOAD_SERVICE,
        {
            CONF_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            CONF_FILENAME: TEST_FILENAME,
            CONF_DESTINATION_FOLDER: DESINATION_FOLDER,
        },
        blocking=True,
        return_response=True,
    )

    assert response
    assert response["files"]
    assert cast(list[dict[str, Any]], response["files"])[0]["id"] == "metadata_id"


async def test_upload_service_no_response(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test service call to upload content without response."""
    await setup_integration(hass, mock_config_entry)

    assert hass.services.has_service(DOMAIN, "upload")

    response = await hass.services.async_call(
        DOMAIN,
        UPLOAD_SERVICE,
        {
            CONF_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            CONF_FILENAME: TEST_FILENAME,
            CONF_DESTINATION_FOLDER: DESINATION_FOLDER,
        },
        blocking=True,
    )

    assert response is None


async def test_upload_service_config_entry_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test upload service call with a config entry that does not exist."""
    await setup_integration(hass, mock_config_entry)
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            UPLOAD_SERVICE,
            {
                CONF_CONFIG_ENTRY_ID: "invalid-config-entry-id",
                CONF_FILENAME: TEST_FILENAME,
                CONF_DESTINATION_FOLDER: DESINATION_FOLDER,
            },
            blocking=True,
            return_response=True,
        )
    assert err.value.translation_key == "service_config_entry_not_found"


async def test_config_entry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test upload service call with a config entry that is not loaded."""
    await setup_integration(hass, mock_config_entry)
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            UPLOAD_SERVICE,
            {
                CONF_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                CONF_FILENAME: TEST_FILENAME,
                CONF_DESTINATION_FOLDER: DESINATION_FOLDER,
            },
            blocking=True,
            return_response=True,
        )
    assert err.value.translation_key == "service_config_entry_not_loaded"


@pytest.mark.parametrize("upload_file", [MockUploadFile(is_allowed_path=False)])
async def test_path_is_not_allowed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test upload service call with a filename path that is not allowed."""
    await setup_integration(hass, mock_config_entry)
    with (
        pytest.raises(HomeAssistantError, match="no access to path"),
    ):
        await hass.services.async_call(
            DOMAIN,
            UPLOAD_SERVICE,
            {
                CONF_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                CONF_FILENAME: TEST_FILENAME,
                CONF_DESTINATION_FOLDER: DESINATION_FOLDER,
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize("upload_file", [MockUploadFile(exists=False)])
async def test_filename_does_not_exist(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test upload service call with a filename path that does not exist."""
    await setup_integration(hass, mock_config_entry)
    with pytest.raises(HomeAssistantError, match="does not exist"):
        await hass.services.async_call(
            DOMAIN,
            UPLOAD_SERVICE,
            {
                CONF_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                CONF_FILENAME: TEST_FILENAME,
                CONF_DESTINATION_FOLDER: DESINATION_FOLDER,
            },
            blocking=True,
            return_response=True,
        )


async def test_upload_service_fails_upload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client: MagicMock,
) -> None:
    """Test service call to upload content."""
    await setup_integration(hass, mock_config_entry)
    mock_onedrive_client.upload_file.side_effect = OneDriveException("error")

    with pytest.raises(HomeAssistantError, match="Failed to upload"):
        await hass.services.async_call(
            DOMAIN,
            UPLOAD_SERVICE,
            {
                CONF_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                CONF_FILENAME: TEST_FILENAME,
                CONF_DESTINATION_FOLDER: DESINATION_FOLDER,
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize("upload_file", [MockUploadFile(size=260 * 1024 * 1024)])
async def test_upload_size_limit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test upload service call with a filename path that does not exist."""
    await setup_integration(hass, mock_config_entry)
    with pytest.raises(
        HomeAssistantError,
        match=re.escape(f"`{TEST_FILENAME}` is too large (272629760 > 262144000)"),
    ):
        await hass.services.async_call(
            DOMAIN,
            UPLOAD_SERVICE,
            {
                CONF_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                CONF_FILENAME: TEST_FILENAME,
                CONF_DESTINATION_FOLDER: DESINATION_FOLDER,
            },
            blocking=True,
            return_response=True,
        )


async def test_create_album_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client: MagicMock,
) -> None:
    """Test service call when folder creation fails."""
    await setup_integration(hass, mock_config_entry)
    assert hass.services.has_service(DOMAIN, "upload")

    mock_onedrive_client.create_folder.side_effect = OneDriveException()

    with pytest.raises(HomeAssistantError, match="Failed to create folder"):
        await hass.services.async_call(
            DOMAIN,
            UPLOAD_SERVICE,
            {
                CONF_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                CONF_FILENAME: TEST_FILENAME,
                CONF_DESTINATION_FOLDER: DESINATION_FOLDER,
            },
            blocking=True,
            return_response=True,
        )


async def test_delete_service_config_entry_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test delete service call with a config entry that does not exist."""
    await setup_integration(hass, mock_config_entry)
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            DELETE_SERVICE,
            {
                CONF_CONFIG_ENTRY_ID: "invalid-config-entry-id",
                CONF_DESTINATION_PATH: [TEST_DESTINATION_PATH],
            },
            blocking=True,
        )
    assert err.value.translation_key == "service_config_entry_not_found"


async def test_delete_service_config_entry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test delete service call with a config entry that is not loaded."""
    await setup_integration(hass, mock_config_entry)
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            DELETE_SERVICE,
            {
                CONF_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                CONF_DESTINATION_PATH: [TEST_DESTINATION_PATH],
            },
            blocking=True,
        )
    assert err.value.translation_key == "service_config_entry_not_loaded"


async def test_delete_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client: MagicMock,
) -> None:
    """Test delete service call removes the remote file."""
    await setup_integration(hass, mock_config_entry)

    assert hass.services.has_service(DOMAIN, DELETE_SERVICE)

    await hass.services.async_call(
        DOMAIN,
        DELETE_SERVICE,
        {
            CONF_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            CONF_DESTINATION_PATH: [TEST_DESTINATION_PATH],
        },
        blocking=True,
    )

    mock_onedrive_client.delete_drive_item.assert_called_once()
    call_args = mock_onedrive_client.delete_drive_item.call_args
    assert call_args.args[0] == f"id:/{TEST_DESTINATION_PATH}:"
    assert call_args.args[1] is False


async def test_delete_service_delete_permanently(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client: MagicMock,
) -> None:
    """Test delete service passes delete_permanently=True when option is set."""
    await setup_integration(hass, mock_config_entry)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={"delete_permanently": True}
    )

    await hass.services.async_call(
        DOMAIN,
        DELETE_SERVICE,
        {
            CONF_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            CONF_DESTINATION_PATH: [TEST_DESTINATION_PATH],
        },
        blocking=True,
    )

    call_args = mock_onedrive_client.delete_drive_item.call_args
    assert call_args.args[0] == f"id:/{TEST_DESTINATION_PATH}:"
    assert call_args.args[1] is True


async def test_delete_service_multiple_files(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client: MagicMock,
) -> None:
    """Test delete service removes multiple remote files in parallel."""
    await setup_integration(hass, mock_config_entry)
    second_path = "photos/snapshots/image2.jpg"

    await hass.services.async_call(
        DOMAIN,
        DELETE_SERVICE,
        {
            CONF_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            CONF_DESTINATION_PATH: [TEST_DESTINATION_PATH, second_path],
        },
        blocking=True,
    )

    assert mock_onedrive_client.delete_drive_item.call_count == 2
    called_paths = {
        c.args[0] for c in mock_onedrive_client.delete_drive_item.call_args_list
    }
    assert called_paths == {
        f"id:/{TEST_DESTINATION_PATH}:",
        f"id:/{second_path}:",
    }


async def test_delete_service_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client: MagicMock,
) -> None:
    """Test delete service raises HomeAssistantError on OneDriveException."""
    await setup_integration(hass, mock_config_entry)
    mock_onedrive_client.delete_drive_item.side_effect = OneDriveException("api error")

    with pytest.raises(HomeAssistantError, match="Failed to delete file"):
        await hass.services.async_call(
            DOMAIN,
            DELETE_SERVICE,
            {
                CONF_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                CONF_DESTINATION_PATH: [TEST_DESTINATION_PATH],
            },
            blocking=True,
        )


async def test_delete_service_get_approot_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client: MagicMock,
) -> None:
    """Test delete service raises HomeAssistantError when get_approot fails."""
    await setup_integration(hass, mock_config_entry)
    mock_onedrive_client.get_approot.side_effect = OneDriveException("network error")

    with pytest.raises(HomeAssistantError, match="Failed to delete file"):
        await hass.services.async_call(
            DOMAIN,
            DELETE_SERVICE,
            {
                CONF_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                CONF_DESTINATION_PATH: [TEST_DESTINATION_PATH],
            },
            blocking=True,
        )


async def test_delete_service_unexpected_exception(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client: MagicMock,
) -> None:
    """Test delete service re-raises non-OneDrive exceptions from asyncio.gather."""
    await setup_integration(hass, mock_config_entry)
    mock_onedrive_client.delete_drive_item.side_effect = RuntimeError("unexpected")

    with pytest.raises(RuntimeError, match="unexpected"):
        await hass.services.async_call(
            DOMAIN,
            DELETE_SERVICE,
            {
                CONF_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                CONF_DESTINATION_PATH: [TEST_DESTINATION_PATH],
            },
            blocking=True,
        )


async def test_delete_empty_destination_path(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test delete service raises when destination_path is an empty list."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises((HomeAssistantError, ServiceValidationError, vol.Invalid)):
        await hass.services.async_call(
            DOMAIN,
            DELETE_SERVICE,
            {
                CONF_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                CONF_DESTINATION_PATH: [],
            },
            blocking=True,
        )


@pytest.mark.parametrize(
    "bad_path",
    [
        "",
        "/",
        "//",
        "photos/../secrets",
        "photos/file:name.jpg",
        "../escape",
    ],
)
async def test_delete_invalid_destination_path(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    bad_path: str,
) -> None:
    """Test delete service raises HomeAssistantError for invalid destination paths."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError, match="Invalid destination path"):
        await hass.services.async_call(
            DOMAIN,
            DELETE_SERVICE,
            {
                CONF_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                CONF_DESTINATION_PATH: bad_path,
            },
            blocking=True,
        )
