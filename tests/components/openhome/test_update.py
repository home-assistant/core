"""Tests for the Openhome update platform."""

from unittest.mock import MagicMock

from openhomedevice.exceptions import OpenhomeConnectionError
import pytest

from homeassistant.components.update import (
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    ATTR_RELEASE_SUMMARY,
    ATTR_RELEASE_URL,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
    UpdateDeviceClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration

from tests.common import MockConfigEntry

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


ENTITY_ID = "update.friendly_name"


@pytest.fixture
def platforms() -> list[Platform]:
    """Only load the update platform."""
    return [Platform.UPDATE]


async def test_not_supported(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_device: MagicMock
) -> None:
    """Ensure update entity works if service not supported."""
    mock_device.software_status.return_value = None

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)

    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_DEVICE_CLASS] == UpdateDeviceClass.FIRMWARE
    assert state.attributes[ATTR_INSTALLED_VERSION] is None
    assert state.attributes[ATTR_LATEST_VERSION] is None
    assert state.attributes[ATTR_RELEASE_URL] is None
    assert state.attributes[ATTR_RELEASE_SUMMARY] is None
    mock_device.update_firmware.assert_not_called()


async def test_on_latest_firmware(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_device: MagicMock
) -> None:
    """Test device on latest firmware."""

    mock_device.software_status.return_value = LATEST_FIRMWARE_INSTALLED

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)

    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_DEVICE_CLASS] == UpdateDeviceClass.FIRMWARE
    assert state.attributes[ATTR_INSTALLED_VERSION] == "4.100.502"
    assert state.attributes[ATTR_LATEST_VERSION] is None
    assert state.attributes[ATTR_RELEASE_URL] is None
    assert state.attributes[ATTR_RELEASE_SUMMARY] is None
    mock_device.update_firmware.assert_not_called()


async def test_update_available(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_device: MagicMock
) -> None:
    """Test device has firmware update available."""

    mock_device.software_status.return_value = FIRMWARE_UPDATE_AVAILABLE

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)

    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_DEVICE_CLASS] == UpdateDeviceClass.FIRMWARE
    assert state.attributes[ATTR_INSTALLED_VERSION] == "4.99.491"
    assert state.attributes[ATTR_LATEST_VERSION] == "4.100.502"
    assert (
        state.attributes[ATTR_RELEASE_URL]
        == "http://docs.linn.co.uk/wiki/index.php/ReleaseNotes"
    )
    assert (
        state.attributes[ATTR_RELEASE_SUMMARY]
        == "Release build version 4.100.502 (07 Jun 2023 12:29:48)"
    )

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_device.update_firmware.assert_awaited_once()


async def test_firmware_update_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_device: MagicMock
) -> None:
    """Ensure a failed firmware install is raised to the user."""
    mock_device.software_status.return_value = FIRMWARE_UPDATE_AVAILABLE
    mock_device.update_firmware.side_effect = OpenhomeConnectionError(
        "no route to host"
    )

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
    mock_device.update_firmware.assert_awaited_once()


async def test_firmware_update_not_required(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_device: MagicMock
) -> None:
    """Ensure firmware install does nothing if up to date."""

    mock_device.software_status.return_value = LATEST_FIRMWARE_INSTALLED

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
    mock_device.update_firmware.assert_not_called()
