"""Tests for the Openhome update platform."""
from unittest.mock import AsyncMock

from homeassistant.components.openhome.update import OpenhomeUpdateEntity

LATEST_FIRMWARE_INSTALLED = {
    "status": "on_latest",
    "current_software": {"version": "4.100.502", "topic": "main", "channel": "release"},
}

FIRMWARE_UPDATE_AVAILABLE = {
    "status": "update_available",
    "current_software": {"version": "4.99.491", "topic": "main", "channel": "release"},
    "update_info": {
        "legal": {
            "licenseurl": "http://products.linn.co.uk/VersionInfo/licenseV2.txt",
            "privacyurl": "https://www.linn.co.uk/privacy",
            "privacyuri": "https://products.linn.co.uk/VersionInfo/PrivacyV1.json",
            "privacyversion": 1,
        },
        "releasenotesuri": "http://docs.linn.co.uk/wiki/index.php/ReleaseNotes",
        "updates": [
            {
                "channel": "release",
                "date": "07 Jun 2023 12:29:48",
                "description": "Release build version 4.100.502 (07 Jun 2023 12:29:48)",
                "exaktlink": "3",
                "manifest": "https://cloud.linn.co.uk/update/components/836/4.100.502/manifest.json",
                "topic": "main",
                "variant": "836",
                "version": "4.100.502",
            }
        ],
        "exaktUpdates": [],
    },
}


async def test_on_latest_firmware():
    """Test device on latest firmware."""
    mock_device = AsyncMock()

    mock_device.software_status.return_value = LATEST_FIRMWARE_INSTALLED
    entity = OpenhomeUpdateEntity(mock_device)
    await entity.async_update()

    assert entity.installed_version == "4.100.502"
    assert entity.latest_version is None
    assert entity.release_url is None
    assert entity.release_summary is None


async def test_update_available():
    """Test device has firmware update available."""
    mock_device = AsyncMock()

    mock_device.software_status.return_value = FIRMWARE_UPDATE_AVAILABLE
    entity = OpenhomeUpdateEntity(mock_device)
    await entity.async_update()

    assert entity.installed_version == "4.99.491"
    assert entity.latest_version == "4.100.502"
    assert entity.release_url == "http://docs.linn.co.uk/wiki/index.php/ReleaseNotes"
    assert (
        entity.release_summary
        == "Release build version 4.100.502 (07 Jun 2023 12:29:48)"
    )


async def test_firmware_update():
    """Test requesting firmware update."""
    mock_device = AsyncMock()

    mock_device.software_status.return_value = FIRMWARE_UPDATE_AVAILABLE
    entity = OpenhomeUpdateEntity(mock_device)
    await entity.async_update()
    await entity.async_install(None, False)

    mock_device.update_firmware.assert_called_once()


async def test_not_supported():
    """Ensure update entity works if service not supported."""
    mock_device = AsyncMock()

    mock_device.software_status.return_value = None
    entity = OpenhomeUpdateEntity(mock_device)
    await entity.async_update()
    await entity.async_install(None, False)

    assert entity.installed_version is None
    assert entity.latest_version is None
    assert entity.release_url is None
    assert entity.release_summary is None
    mock_device.update_firmware.assert_not_called()


async def test_firmware_update_not_required():
    """Ensure firmware install does nothing if up to date."""
    mock_device = AsyncMock()

    mock_device.software_status.return_value = LATEST_FIRMWARE_INSTALLED
    entity = OpenhomeUpdateEntity(mock_device)
    await entity.async_install(None, False)

    mock_device.update_firmware.assert_not_called()
