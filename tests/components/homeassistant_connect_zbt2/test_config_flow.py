"""Test the Home Assistant Connect ZBT-2 config flow."""

from unittest.mock import patch

import pytest

from homeassistant.components.homeassistant_connect_zbt2.const import DOMAIN
from homeassistant.components.homeassistant_hardware.firmware_config_flow import (
    STEP_PICK_FIRMWARE_THREAD,
    STEP_PICK_FIRMWARE_ZIGBEE,
)
from homeassistant.components.homeassistant_hardware.util import (
    ApplicationType,
    FirmwareInfo,
)
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from .common import USB_DATA_ZBT2

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("step", "usb_data", "model", "fw_type", "fw_version"),
    [
        (
            STEP_PICK_FIRMWARE_ZIGBEE,
            USB_DATA_ZBT2,
            "Home Assistant Connect ZBT-2",
            ApplicationType.EZSP,
            "7.4.4.0 build 0",
        ),
        (
            STEP_PICK_FIRMWARE_THREAD,
            USB_DATA_ZBT2,
            "Home Assistant Connect ZBT-2",
            ApplicationType.SPINEL,
            "2.4.4.0",
        ),
    ],
)
async def test_config_flow(
    step: str,
    usb_data: UsbServiceInfo,
    model: str,
    fw_type: ApplicationType,
    fw_version: str,
    hass: HomeAssistant,
) -> None:
    """Test the config flow for Connect ZBT-2."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "usb"}, data=usb_data
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "pick_firmware"
    assert result["description_placeholders"]["model"] == model

    async def mock_install_firmware_step(
        self,
        fw_update_url: str,
        fw_type: str,
        firmware_name: str,
        expected_installed_firmware_type: ApplicationType,
        step_id: str,
        next_step_id: str,
    ) -> ConfigFlowResult:
        if next_step_id == "start_otbr_addon":
            next_step_id = "pre_confirm_otbr"

        return await getattr(self, f"async_step_{next_step_id}")(user_input={})

    with (
        patch(
            "homeassistant.components.homeassistant_hardware.firmware_config_flow.BaseFirmwareConfigFlow._ensure_thread_addon_setup",
            return_value=None,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.firmware_config_flow.BaseFirmwareConfigFlow._install_firmware_step",
            autospec=True,
            side_effect=mock_install_firmware_step,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.firmware_config_flow.probe_silabs_firmware_info",
            return_value=FirmwareInfo(
                device=usb_data.device,
                firmware_type=fw_type,
                firmware_version=fw_version,
                owners=[],
                source="probe",
            ),
        ),
    ):
        confirm_result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": step},
        )

        assert confirm_result["type"] is FlowResultType.FORM
        assert confirm_result["step_id"] == (
            "confirm_zigbee" if step == STEP_PICK_FIRMWARE_ZIGBEE else "confirm_otbr"
        )

        create_result = await hass.config_entries.flow.async_configure(
            confirm_result["flow_id"], user_input={}
        )

    assert create_result["type"] is FlowResultType.CREATE_ENTRY
    config_entry = create_result["result"]
    assert config_entry.data == {
        "firmware": fw_type.value,
        "firmware_version": fw_version,
        "device": usb_data.device,
        "manufacturer": usb_data.manufacturer,
        "pid": usb_data.pid,
        "product": usb_data.description,
        "serial_number": usb_data.serial_number,
        "vid": usb_data.vid,
    }

    flows = hass.config_entries.flow.async_progress()

    if step == STEP_PICK_FIRMWARE_ZIGBEE:
        # Ensure a ZHA discovery flow has been created
        assert len(flows) == 1
        zha_flow = flows[0]
        assert zha_flow["handler"] == "zha"
        assert zha_flow["context"]["source"] == "hardware"
        assert zha_flow["step_id"] == "confirm"
    else:
        assert len(flows) == 0


@pytest.mark.parametrize(
    ("usb_data", "model"),
    [
        (USB_DATA_ZBT2, "Home Assistant Connect ZBT-2"),
    ],
)
async def test_options_flow(
    usb_data: UsbServiceInfo, model: str, hass: HomeAssistant
) -> None:
    """Test the options flow for Connect ZBT-2."""
    config_entry = MockConfigEntry(
        domain="homeassistant_connect_zbt2",
        data={
            "firmware": "spinel",
            "firmware_version": "SL-OPENTHREAD/2.4.4.0_GitHub-7074a43e4",
            "device": usb_data.device,
            "manufacturer": usb_data.manufacturer,
            "pid": usb_data.pid,
            "product": usb_data.description,
            "serial_number": usb_data.serial_number,
            "vid": usb_data.vid,
        },
        version=1,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)

    # First step is confirmation
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "pick_firmware"
    assert result["description_placeholders"]["firmware_type"] == "spinel"
    assert result["description_placeholders"]["model"] == model

    async def mock_async_step_pick_firmware_zigbee(self, data):
        return await self.async_step_pre_confirm_zigbee()

    with (
        patch(
            "homeassistant.components.homeassistant_hardware.firmware_config_flow.BaseFirmwareOptionsFlow.async_step_pick_firmware_zigbee",
            autospec=True,
            side_effect=mock_async_step_pick_firmware_zigbee,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.firmware_config_flow.probe_silabs_firmware_info",
            return_value=FirmwareInfo(
                device=usb_data.device,
                firmware_type=ApplicationType.EZSP,
                firmware_version="7.4.4.0 build 0",
                owners=[],
                source="probe",
            ),
        ),
    ):
        confirm_result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )

        assert confirm_result["type"] is FlowResultType.FORM
        assert confirm_result["step_id"] == "confirm_zigbee"

        create_result = await hass.config_entries.options.async_configure(
            confirm_result["flow_id"], user_input={}
        )

    assert create_result["type"] is FlowResultType.CREATE_ENTRY

    assert config_entry.data == {
        "firmware": "ezsp",
        "firmware_version": "7.4.4.0 build 0",
        "device": usb_data.device,
        "manufacturer": usb_data.manufacturer,
        "pid": usb_data.pid,
        "product": usb_data.description,
        "serial_number": usb_data.serial_number,
        "vid": usb_data.vid,
    }


async def test_duplicate_discovery(hass: HomeAssistant) -> None:
    """Test config flow unique_id deduplication."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "usb"}, data=USB_DATA_ZBT2
    )

    assert result["type"] is FlowResultType.MENU

    result_duplicate = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "usb"}, data=USB_DATA_ZBT2
    )

    assert result_duplicate["type"] is FlowResultType.ABORT
    assert result_duplicate["reason"] == "already_in_progress"


async def test_duplicate_discovery_updates_usb_path(hass: HomeAssistant) -> None:
    """Test config flow unique_id deduplication updates USB path."""
    config_entry = MockConfigEntry(
        domain="homeassistant_connect_zbt2",
        data={
            "firmware": "spinel",
            "firmware_version": "SL-OPENTHREAD/2.4.4.0_GitHub-7074a43e4",
            "device": "/dev/oldpath",
            "manufacturer": USB_DATA_ZBT2.manufacturer,
            "pid": USB_DATA_ZBT2.pid,
            "product": USB_DATA_ZBT2.description,
            "serial_number": USB_DATA_ZBT2.serial_number,
            "vid": USB_DATA_ZBT2.vid,
        },
        version=1,
        minor_version=1,
        unique_id=(
            f"{USB_DATA_ZBT2.vid}:{USB_DATA_ZBT2.pid}_"
            f"{USB_DATA_ZBT2.serial_number}_"
            f"{USB_DATA_ZBT2.manufacturer}_"
            f"{USB_DATA_ZBT2.description}"
        ),
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "usb"}, data=USB_DATA_ZBT2
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert config_entry.data["device"] == USB_DATA_ZBT2.device
