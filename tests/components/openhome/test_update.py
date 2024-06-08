"""Tests for the Openhome update platform."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.openhome.const import DOMAIN
from homeassistant.components.update import (
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    ATTR_RELEASE_SUMMARY,
    ATTR_RELEASE_URL,
    DOMAIN as PLATFORM_DOMAIN,
    SERVICE_INSTALL,
    UpdateDeviceClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    CONF_HOST,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

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


async def setup_integration(
    hass: HomeAssistant,
    software_status: dict,
    update_firmware: AsyncMock,
) -> None:
    """Load an openhome platform with mocked device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "http://localhost"},
    )
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.openhome.PLATFORMS", [Platform.UPDATE]),
        patch("homeassistant.components.openhome.Device", MagicMock()) as mock_device,
    ):
        mock_device.return_value.init = AsyncMock()
        mock_device.return_value.uuid = MagicMock(return_value="uuid")
        mock_device.return_value.manufacturer = MagicMock(return_value="manufacturer")
        mock_device.return_value.model_name = MagicMock(return_value="model_name")
        mock_device.return_value.friendly_name = MagicMock(return_value="friendly_name")
        mock_device.return_value.software_status = AsyncMock(
            return_value=software_status
        )
        mock_device.return_value.update_firmware = update_firmware
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def test_not_supported(hass: HomeAssistant) -> None:
    """Ensure update entity works if service not supported."""

    update_firmware = AsyncMock()
    await setup_integration(hass, None, update_firmware)

    state = hass.states.get("update.friendly_name")

    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_DEVICE_CLASS] == UpdateDeviceClass.FIRMWARE
    assert state.attributes[ATTR_INSTALLED_VERSION] is None
    assert state.attributes[ATTR_LATEST_VERSION] is None
    assert state.attributes[ATTR_RELEASE_URL] is None
    assert state.attributes[ATTR_RELEASE_SUMMARY] is None
    update_firmware.assert_not_called()


async def test_on_latest_firmware(hass: HomeAssistant) -> None:
    """Test device on latest firmware."""

    update_firmware = AsyncMock()
    await setup_integration(hass, LATEST_FIRMWARE_INSTALLED, update_firmware)

    state = hass.states.get("update.friendly_name")

    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_DEVICE_CLASS] == UpdateDeviceClass.FIRMWARE
    assert state.attributes[ATTR_INSTALLED_VERSION] == "4.100.502"
    assert state.attributes[ATTR_LATEST_VERSION] is None
    assert state.attributes[ATTR_RELEASE_URL] is None
    assert state.attributes[ATTR_RELEASE_SUMMARY] is None
    update_firmware.assert_not_called()


async def test_update_available(hass: HomeAssistant) -> None:
    """Test device has firmware update available."""

    update_firmware = AsyncMock()
    await setup_integration(hass, FIRMWARE_UPDATE_AVAILABLE, update_firmware)

    state = hass.states.get("update.friendly_name")

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
        PLATFORM_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.friendly_name"},
        blocking=True,
    )
    await hass.async_block_till_done()

    update_firmware.assert_called_once()


async def test_firmware_update_not_required(hass: HomeAssistant) -> None:
    """Ensure firmware install does nothing if up to date."""

    update_firmware = AsyncMock()
    await setup_integration(hass, LATEST_FIRMWARE_INSTALLED, update_firmware)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            PLATFORM_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.friendly_name"},
            blocking=True,
        )
    update_firmware.assert_not_called()
