"""Test SkyConnect firmware update entity."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

from ha_silabs_firmware_client import FirmwareManifest, FirmwareMetadata
from yarl import URL

from homeassistant.components.homeassistant_hardware.helpers import (
    async_notify_firmware_info,
)
from homeassistant.components.homeassistant_hardware.util import (
    ApplicationType,
    FirmwareInfo,
    OwningIntegration,
)
from homeassistant.components.homeassistant_sky_connect.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .common import USB_DATA_ZBT1

from tests.common import MockConfigEntry

UPDATE_ENTITY_ID = (
    "update.homeassistant_sky_connect_9e2adbd75b8beb119fe564a0f320645d_firmware"
)


@patch(
    "homeassistant.components.homeassistant_hardware.coordinator.FirmwareUpdateClient",
    autospec=True,
)
async def test_zbt1_update_entity(
    mock_update_client: Mock, hass: HomeAssistant
) -> None:
    """Test the ZBT-1 firmware update entity."""
    mock_update_client.return_value.async_update_data.return_value = FirmwareManifest(
        url=URL("https://example.org/firmware"),
        html_url=URL("https://example.org/release_notes"),
        created_at=dt_util.utcnow(),
        firmwares=(
            FirmwareMetadata(
                filename="skyconnect_zigbee_ncp_test.gbl",
                checksum="aaa",
                size=123,
                release_notes="Some release notes go here",
                metadata={
                    "baudrate": 115200,
                    "ezsp_version": "7.4.4.0",
                    "fw_type": "zigbee_ncp",
                    "fw_variant": None,
                    "metadata_version": 2,
                    "sdk_version": "4.4.4",
                },
                url=URL("https://example.org/firmwares/skyconnect_zigbee_ncp_test.gbl"),
            ),
        ),
    )

    await async_setup_component(hass, "homeassistant", {})

    # Set up the ZBT-1 integration
    zbt1_config_entry = MockConfigEntry(
        domain="homeassistant_sky_connect",
        data={
            "firmware": "ezsp",
            "firmware_version": "7.3.1.0 build 0",
            "device": USB_DATA_ZBT1.device,
            "manufacturer": USB_DATA_ZBT1.manufacturer,
            "pid": USB_DATA_ZBT1.pid,
            "product": USB_DATA_ZBT1.description,
            "serial_number": USB_DATA_ZBT1.serial_number,
            "vid": USB_DATA_ZBT1.vid,
        },
        version=1,
        minor_version=3,
    )
    zbt1_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(zbt1_config_entry.entry_id)
    await hass.async_block_till_done()

    # And also ZHA
    zha_config_entry = MockConfigEntry(
        domain="zha",
        data={
            "device": {
                "path": USB_DATA_ZBT1.device,
                "flow_control": "hardware",
                "baudrate": 115200,
            },
            "radio_type": "ezsp",
        },
        version=4,
    )
    zha_config_entry.add_to_hass(hass)
    zha_config_entry.mock_state(hass, ConfigEntryState.LOADED)

    # Pretend ZHA loaded and notified hardware of the running firmware
    await async_notify_firmware_info(
        hass,
        DOMAIN,
        FirmwareInfo(
            device=USB_DATA_ZBT1.device,
            firmware_type=ApplicationType.EZSP,
            firmware_version="7.3.1.0 build 0",
            owners=[OwningIntegration(config_entry_id=zha_config_entry.entry_id)],
            source="zha",
        ),
    )

    state_before_update = hass.states.get(UPDATE_ENTITY_ID)
    assert state_before_update.state == "unknown"
    assert state_before_update.attributes["title"] == "EmberZNet"
    assert state_before_update.attributes["installed_version"] == "7.3.1.0"
    assert state_before_update.attributes["latest_version"] is None

    # When we check for an update, one will be shown
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {"entity_id": UPDATE_ENTITY_ID},
        blocking=True,
    )
    state_after_update = hass.states.get(UPDATE_ENTITY_ID)
    assert state_after_update.state == "on"
    assert state_after_update.attributes["title"] == "EmberZNet"
    assert state_after_update.attributes["installed_version"] == "7.3.1.0"
    assert state_after_update.attributes["latest_version"] == "7.4.4.0"
    assert state_after_update.attributes["release_summary"] == (
        "Some release notes go here"
    )
    assert state_after_update.attributes["release_url"] == (
        "https://example.org/release_notes"
    )

    mock_firmware = Mock()
    mock_flasher = AsyncMock()

    async def mock_flash_firmware(fw_image, progress_callback):
        await asyncio.sleep(0)
        progress_callback(0, 100)
        await asyncio.sleep(0)
        progress_callback(50, 100)
        await asyncio.sleep(0)
        progress_callback(100, 100)

    mock_flasher.flash_firmware = mock_flash_firmware

    # When we install it, ZHA is reloaded
    with (
        patch(
            "homeassistant.components.homeassistant_hardware.update.parse_firmware_image",
            return_value=mock_firmware,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.update.Flasher",
            return_value=mock_flasher,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.update.probe_silabs_firmware_info",
            return_value=FirmwareInfo(
                device=USB_DATA_ZBT1.device,
                firmware_type=ApplicationType.EZSP,
                firmware_version="7.4.4.0 build 0",
                owners=[],
                source="probe",
            ),
        ),
    ):
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": UPDATE_ENTITY_ID},
            blocking=True,
        )

    # After the firmware update, the entity has the new version and the correct state
    state_after_install = hass.states.get(UPDATE_ENTITY_ID)
    assert state_after_install.state == "off"
    assert state_after_install.attributes["title"] == "EmberZNet"
    assert state_after_install.attributes["installed_version"] == "7.4.4.0"
    assert state_after_install.attributes["latest_version"] == "7.4.4.0"
