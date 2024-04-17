"""Test the Home Assistant SkyConnect config flow."""

from unittest.mock import Mock, call, patch

import pytest
from universal_silabs_flasher.const import ApplicationType

from homeassistant.components import usb
from homeassistant.components.hassio.addon_manager import AddonInfo, AddonState
from homeassistant.components.homeassistant_sky_connect.config_flow import (
    STEP_PICK_FIRMWARE_THREAD,
    STEP_PICK_FIRMWARE_ZIGBEE,
)
from homeassistant.components.homeassistant_sky_connect.const import DOMAIN
from homeassistant.components.homeassistant_sky_connect.util import (
    get_otbr_addon_manager,
    get_zigbee_flasher_addon_manager,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

USB_DATA_SKY = usb.UsbServiceInfo(
    device="/dev/serial/by-id/usb-Nabu_Casa_SkyConnect_v1.0_9e2adbd75b8beb119fe564a0f320645d-if00-port0",
    vid="10C4",
    pid="EA60",
    serial_number="9e2adbd75b8beb119fe564a0f320645d",
    manufacturer="Nabu Casa",
    description="SkyConnect v1.0",
)

USB_DATA_ZBT1 = usb.UsbServiceInfo(
    device="/dev/serial/by-id/usb-Nabu_Casa_Home_Assistant_Connect_ZBT-1_9e2adbd75b8beb119fe564a0f320645d-if00-port0",
    vid="10C4",
    pid="EA60",
    serial_number="9e2adbd75b8beb119fe564a0f320645d",
    manufacturer="Nabu Casa",
    description="Home Assistant Connect ZBT-1",
)


@pytest.mark.parametrize(
    ("usb_data", "model"),
    [
        (USB_DATA_SKY, "Home Assistant SkyConnect"),
        (USB_DATA_ZBT1, "Home Assistant Connect ZBT-1"),
    ],
)
async def test_config_flow_zigbee(
    usb_data: usb.UsbServiceInfo, model: str, hass: HomeAssistant
) -> None:
    """Test the config flow for SkyConnect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "usb"}, data=usb_data
    )

    # First step is confirmation, we haven't probed the firmware yet
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"]["firmware_type"] == "unknown"
    assert result["description_placeholders"]["model"] == model

    # Next, we probe the firmware
    with patch(
        "homeassistant.components.homeassistant_sky_connect.config_flow.probe_silabs_firmware_type",
        return_value=ApplicationType.EZSP,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "pick_firmware"
    assert result["description_placeholders"]["firmware_type"] == ApplicationType.EZSP

    # Set up Zigbee firmware
    mock_flasher_manager = Mock(spec_set=get_zigbee_flasher_addon_manager(hass))

    with (
        patch(
            "homeassistant.components.homeassistant_sky_connect.config_flow.get_zigbee_flasher_addon_manager",
            return_value=mock_flasher_manager,
        ),
        patch(
            "homeassistant.components.homeassistant_sky_connect.config_flow.is_hassio",
            return_value=True,
        ),
    ):
        mock_flasher_manager.addon_name = "Silicon Labs Flasher"
        mock_flasher_manager.async_get_addon_info.return_value = AddonInfo(
            available=True,
            hostname=None,
            options={},
            state=AddonState.NOT_INSTALLED,
            update_available=False,
            version=None,
        )

        # Pick the menu option
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["progress_action"] == "install_addon"
        assert result["step_id"] == "install_zigbee_flasher_addon"

        await hass.async_block_till_done(wait_background_tasks=True)

        mock_flasher_manager.async_get_addon_info.return_value = AddonInfo(
            available=True,
            hostname=None,
            options={
                "device": "",
                "baudrate": 115200,
                "bootloader_baudrate": 115200,
                "flow_control": True,
            },
            state=AddonState.NOT_RUNNING,
            update_available=False,
            version="1.2.3",
        )

        # Progress the flow, it is now configuring the addon and running it
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "run_zigbee_flasher_addon"
        assert result["progress_action"] == "run_zigbee_flasher_addon"

        assert mock_flasher_manager.async_set_addon_options.mock_calls == [
            call(
                {
                    "device": usb_data.device,
                    "baudrate": 115200,
                    "bootloader_baudrate": 115200,
                    "flow_control": True,
                }
            )
        ]

        await hass.async_block_till_done(wait_background_tasks=True)

        # We are finally done
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.data == {
        "firmware": "ezsp",
        "device": usb_data.device,
        "manufacturer": usb_data.manufacturer,
        "pid": usb_data.pid,
        "product": usb_data.description,
        "serial_number": usb_data.serial_number,
        "vid": usb_data.vid,
    }


@pytest.mark.parametrize(
    ("usb_data", "model"),
    [
        (USB_DATA_SKY, "Home Assistant SkyConnect"),
        (USB_DATA_ZBT1, "Home Assistant Connect ZBT-1"),
    ],
)
async def test_config_flow_thread(
    usb_data: usb.UsbServiceInfo, model: str, hass: HomeAssistant
) -> None:
    """Test the config flow for SkyConnect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "usb"}, data=usb_data
    )

    # First step is confirmation, we haven't probed the firmware yet
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"]["firmware_type"] == "unknown"
    assert result["description_placeholders"]["model"] == model

    # Next, we probe the firmware
    with patch(
        "homeassistant.components.homeassistant_sky_connect.config_flow.probe_silabs_firmware_type",
        return_value=ApplicationType.EZSP,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "pick_firmware"
    assert result["description_placeholders"]["firmware_type"] == ApplicationType.EZSP

    # Set up Thread firmware
    mock_otbr_manager = Mock(spec_set=get_otbr_addon_manager(hass))

    with (
        patch(
            "homeassistant.components.homeassistant_sky_connect.config_flow.get_otbr_addon_manager",
            return_value=mock_otbr_manager,
        ),
        patch(
            "homeassistant.components.homeassistant_sky_connect.config_flow.is_hassio",
            return_value=True,
        ),
    ):
        mock_otbr_manager.addon_name = "OpenThread Border Router"
        mock_otbr_manager.async_get_addon_info.return_value = AddonInfo(
            available=True,
            hostname=None,
            options={},
            state=AddonState.NOT_INSTALLED,
            update_available=False,
            version=None,
        )

        # Pick the menu option
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_THREAD},
        )

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["progress_action"] == "install_addon"
        assert result["step_id"] == "install_otbr_addon"

        await hass.async_block_till_done(wait_background_tasks=True)

        mock_otbr_manager.async_get_addon_info.return_value = AddonInfo(
            available=True,
            hostname=None,
            options={
                "device": "",
                "baudrate": 460800,
                "flow_control": True,
                "autoflash_firmware": True,
            },
            state=AddonState.NOT_RUNNING,
            update_available=False,
            version="1.2.3",
        )

        # Progress the flow, it is now configuring the addon and running it
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "start_otbr_addon"
        assert result["progress_action"] == "start_otbr_addon"

        assert mock_otbr_manager.async_set_addon_options.mock_calls == [
            call(
                {
                    "device": usb_data.device,
                    "baudrate": 460800,
                    "flow_control": True,
                    "autoflash_firmware": True,
                }
            )
        ]

        await hass.async_block_till_done(wait_background_tasks=True)

        # We are finally done
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.data == {
        "firmware": "spinel",
        "device": usb_data.device,
        "manufacturer": usb_data.manufacturer,
        "pid": usb_data.pid,
        "product": usb_data.description,
        "serial_number": usb_data.serial_number,
        "vid": usb_data.vid,
    }
