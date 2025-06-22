"""Test the Immich services."""

from pathlib import Path
from unittest.mock import Mock

from aioimmich.exceptions import ImmichError, ImmichNotFoundError
import pytest

from homeassistant.components.immich.const import DOMAIN
from homeassistant.components.immich.services import SERVICE_UPLOAD_FILE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup_services(
    hass: HomeAssistant,
    mock_immich: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup of immich services."""
    await setup_integration(hass, mock_config_entry)

    services = hass.services.async_services_for_domain(DOMAIN)
    assert services
    assert SERVICE_UPLOAD_FILE in services


async def test_upload_file(
    hass: HomeAssistant,
    mock_immich: Mock,
    mock_config_entry: MockConfigEntry,
    tmp_path: Path,
) -> None:
    """Test upload_file service."""
    test_file = tmp_path / "image.png"
    test_file.write_bytes(b"abcdef")

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPLOAD_FILE,
        {
            "config_entry_id": mock_config_entry.entry_id,
            "file": test_file.as_posix(),
        },
        blocking=True,
    )

    mock_immich.assets.async_upload_asset.assert_called_with(test_file.as_posix())
    mock_immich.albums.async_get_album_info.assert_not_called()
    mock_immich.albums.async_add_assets_to_album.assert_not_called()


async def test_upload_file_to_album(
    hass: HomeAssistant,
    mock_immich: Mock,
    mock_config_entry: MockConfigEntry,
    tmp_path: Path,
) -> None:
    """Test upload_file service with target album_id."""
    test_file = tmp_path / "image.png"
    test_file.write_bytes(b"abcdef")

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPLOAD_FILE,
        {
            "config_entry_id": mock_config_entry.entry_id,
            "file": test_file.as_posix(),
            "album_id": "721e1a4b-aa12-441e-8d3b-5ac7ab283bb6",
        },
        blocking=True,
    )

    mock_immich.assets.async_upload_asset.assert_called_with(test_file.as_posix())
    mock_immich.albums.async_get_album_info.assert_called_with(
        "721e1a4b-aa12-441e-8d3b-5ac7ab283bb6", True
    )
    mock_immich.albums.async_add_assets_to_album.assert_called_with(
        "721e1a4b-aa12-441e-8d3b-5ac7ab283bb6", ["abcdef-0123456789"]
    )


async def test_upload_file_config_entry_not_found(
    hass: HomeAssistant,
    mock_immich: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test upload_file service raising config_entry_not_found."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError, match="Config entry not found"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPLOAD_FILE,
            {
                "config_entry_id": "unknown_entry",
                "file": "blabla",
            },
            blocking=True,
        )


async def test_upload_file_config_entry_not_loaded(
    hass: HomeAssistant,
    mock_immich: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test upload_file service raising config_entry_not_loaded."""
    mock_config_entry.disabled_by = er.RegistryEntryDisabler.USER
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError, match="Config entry not loaded"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPLOAD_FILE,
            {
                "config_entry_id": mock_config_entry.entry_id,
                "file": "blabla",
            },
            blocking=True,
        )


async def test_upload_file_file_not_found(
    hass: HomeAssistant,
    mock_immich: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test upload_file service raising file_not_found."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(
        ServiceValidationError, match="File `not_existing.file` not found"
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPLOAD_FILE,
            {
                "config_entry_id": mock_config_entry.entry_id,
                "file": "not_existing.file",
            },
            blocking=True,
        )


async def test_upload_file_album_not_found(
    hass: HomeAssistant,
    mock_immich: Mock,
    mock_config_entry: MockConfigEntry,
    tmp_path: Path,
) -> None:
    """Test upload_file service raising album_not_found."""
    test_file = tmp_path / "image.png"
    test_file.write_bytes(b"abcdef")

    await setup_integration(hass, mock_config_entry)

    mock_immich.albums.async_get_album_info.side_effect = ImmichNotFoundError(
        {
            "message": "Not found or no album.read access",
            "error": "Bad Request",
            "statusCode": 400,
            "correlationId": "nyzxjkno",
        }
    )

    with pytest.raises(
        ServiceValidationError,
        match="Album with ID `721e1a4b-aa12-441e-8d3b-5ac7ab283bb6` not found",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPLOAD_FILE,
            {
                "config_entry_id": mock_config_entry.entry_id,
                "file": test_file.as_posix(),
                "album_id": "721e1a4b-aa12-441e-8d3b-5ac7ab283bb6",
            },
            blocking=True,
        )


async def test_upload_file_upload_failed(
    hass: HomeAssistant,
    mock_immich: Mock,
    mock_config_entry: MockConfigEntry,
    tmp_path: Path,
) -> None:
    """Test upload_file service raising upload_failed."""
    test_file = tmp_path / "image.png"
    test_file.write_bytes(b"abcdef")

    await setup_integration(hass, mock_config_entry)

    mock_immich.assets.async_upload_asset.side_effect = ImmichError(
        {
            "message": "Boom! Upload failed",
            "error": "Bad Request",
            "statusCode": 400,
            "correlationId": "nyzxjkno",
        }
    )
    with pytest.raises(
        ServiceValidationError, match=f"Upload of file `{test_file.as_posix()}` failed"
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPLOAD_FILE,
            {
                "config_entry_id": mock_config_entry.entry_id,
                "file": test_file.as_posix(),
            },
            blocking=True,
        )


async def test_upload_file_to_album_upload_failed(
    hass: HomeAssistant,
    mock_immich: Mock,
    mock_config_entry: MockConfigEntry,
    tmp_path: Path,
) -> None:
    """Test upload_file service with target album_id raising upload_failed."""
    test_file = tmp_path / "image.png"
    test_file.write_bytes(b"abcdef")

    await setup_integration(hass, mock_config_entry)

    mock_immich.albums.async_add_assets_to_album.side_effect = ImmichError(
        {
            "message": "Boom! Add to album failed.",
            "error": "Bad Request",
            "statusCode": 400,
            "correlationId": "nyzxjkno",
        }
    )
    with pytest.raises(
        ServiceValidationError, match=f"Upload of file `{test_file.as_posix()}` failed"
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPLOAD_FILE,
            {
                "config_entry_id": mock_config_entry.entry_id,
                "file": test_file.as_posix(),
                "album_id": "721e1a4b-aa12-441e-8d3b-5ac7ab283bb6",
            },
            blocking=True,
        )
