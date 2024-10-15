"""Test the Home Assistant SkyConnect config flow."""

from unittest.mock import Mock, patch

import pytest

from homeassistant.components import usb
from homeassistant.components.hassio import AddonInfo, AddonState
from homeassistant.components.homeassistant_hardware.firmware_config_flow import (
    STEP_PICK_FIRMWARE_ZIGBEE,
)
from homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon import (
    CONF_DISABLE_MULTI_PAN,
    get_flasher_addon_manager,
    get_multiprotocol_addon_manager,
)
from homeassistant.components.homeassistant_sky_connect.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

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
async def test_config_flow(
    usb_data: usb.UsbServiceInfo, model: str, hass: HomeAssistant
) -> None:
    """Test the config flow for SkyConnect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "usb"}, data=usb_data
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "pick_firmware"
    assert result["description_placeholders"]["model"] == model

    async def mock_async_step_pick_firmware_zigbee(self, data):
        return await self.async_step_confirm_zigbee(user_input={})

    with patch(
        "homeassistant.components.homeassistant_hardware.firmware_config_flow.BaseFirmwareConfigFlow.async_step_pick_firmware_zigbee",
        autospec=True,
        side_effect=mock_async_step_pick_firmware_zigbee,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.data == {
        "firmware": "ezsp",
        "device": usb_data.device,
        "manufacturer": usb_data.manufacturer,
        "pid": usb_data.pid,
        "description": usb_data.description,
        "product": usb_data.description,
        "serial_number": usb_data.serial_number,
        "vid": usb_data.vid,
    }

    # Ensure a ZHA discovery flow has been created
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    zha_flow = flows[0]
    assert zha_flow["handler"] == "zha"
    assert zha_flow["context"]["source"] == "hardware"
    assert zha_flow["step_id"] == "confirm"


@pytest.mark.parametrize(
    ("usb_data", "model"),
    [
        (USB_DATA_SKY, "Home Assistant SkyConnect"),
        (USB_DATA_ZBT1, "Home Assistant Connect ZBT-1"),
    ],
)
async def test_options_flow(
    usb_data: usb.UsbServiceInfo, model: str, hass: HomeAssistant
) -> None:
    """Test the options flow for SkyConnect."""
    config_entry = MockConfigEntry(
        domain="homeassistant_sky_connect",
        data={
            "firmware": "spinel",
            "device": usb_data.device,
            "manufacturer": usb_data.manufacturer,
            "pid": usb_data.pid,
            "description": usb_data.description,
            "product": usb_data.description,
            "serial_number": usb_data.serial_number,
            "vid": usb_data.vid,
        },
        version=1,
        minor_version=2,
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
        return await self.async_step_confirm_zigbee(user_input={})

    with patch(
        "homeassistant.components.homeassistant_hardware.firmware_config_flow.BaseFirmwareOptionsFlow.async_step_pick_firmware_zigbee",
        autospec=True,
        side_effect=mock_async_step_pick_firmware_zigbee,
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"] is True

    assert config_entry.data == {
        "firmware": "ezsp",
        "device": usb_data.device,
        "manufacturer": usb_data.manufacturer,
        "pid": usb_data.pid,
        "description": usb_data.description,
        "product": usb_data.description,
        "serial_number": usb_data.serial_number,
        "vid": usb_data.vid,
    }


@pytest.mark.usefixtures("supervisor_client")
@pytest.mark.parametrize(
    ("usb_data", "model"),
    [
        (USB_DATA_SKY, "Home Assistant SkyConnect"),
        (USB_DATA_ZBT1, "Home Assistant Connect ZBT-1"),
    ],
)
async def test_options_flow_multipan_uninstall(
    usb_data: usb.UsbServiceInfo, model: str, hass: HomeAssistant
) -> None:
    """Test options flow for when multi-PAN firmware is installed."""
    config_entry = MockConfigEntry(
        domain="homeassistant_sky_connect",
        data={
            "firmware": "cpc",
            "device": usb_data.device,
            "manufacturer": usb_data.manufacturer,
            "pid": usb_data.pid,
            "product": usb_data.description,
            "serial_number": usb_data.serial_number,
            "vid": usb_data.vid,
        },
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)

    # Multi-PAN addon is running
    mock_multipan_manager = Mock(spec_set=await get_multiprotocol_addon_manager(hass))
    mock_multipan_manager.async_get_addon_info.return_value = AddonInfo(
        available=True,
        hostname=None,
        options={"device": usb_data.device},
        state=AddonState.RUNNING,
        update_available=False,
        version="1.0.0",
    )

    mock_flasher_manager = Mock(spec_set=get_flasher_addon_manager(hass))
    mock_flasher_manager.async_get_addon_info.return_value = AddonInfo(
        available=True,
        hostname=None,
        options={},
        state=AddonState.NOT_RUNNING,
        update_available=False,
        version="1.0.0",
    )

    with (
        patch(
            "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.get_multiprotocol_addon_manager",
            return_value=mock_multipan_manager,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.get_flasher_addon_manager",
            return_value=mock_flasher_manager,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.is_hassio",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "addon_menu"
        assert "uninstall_addon" in result["menu_options"]

        # Pick the uninstall option
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"next_step_id": "uninstall_addon"},
        )

        # Check the box
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_DISABLE_MULTI_PAN: True}
        )

        # Finish the flow
        result = await hass.config_entries.options.async_configure(result["flow_id"])
        await hass.async_block_till_done(wait_background_tasks=True)
        result = await hass.config_entries.options.async_configure(result["flow_id"])
        await hass.async_block_till_done(wait_background_tasks=True)
        result = await hass.config_entries.options.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.CREATE_ENTRY

    # We've reverted the firmware back to Zigbee
    assert config_entry.data["firmware"] == "ezsp"
