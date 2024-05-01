"""Test the Home Assistant SkyConnect config flow."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, Mock, call, patch

import pytest
from universal_silabs_flasher.const import ApplicationType

from homeassistant.components import usb
from homeassistant.components.hassio.addon_manager import AddonInfo, AddonState
from homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon import (
    CONF_DISABLE_MULTI_PAN,
    get_flasher_addon_manager,
    get_multiprotocol_addon_manager,
)
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


def delayed_side_effect() -> Callable[..., Awaitable[None]]:
    """Slows down eager tasks by delaying for an event loop tick."""

    async def side_effect(*args: Any, **kwargs: Any) -> None:
        await asyncio.sleep(0)

    return side_effect


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
        return_value=ApplicationType.SPINEL,  # Ensure we re-install it
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "pick_firmware"
    assert result["description_placeholders"]["firmware_type"] == "spinel"

    # Set up Zigbee firmware
    mock_flasher_manager = Mock(spec_set=get_zigbee_flasher_addon_manager(hass))
    mock_flasher_manager.async_install_addon_waiting = AsyncMock(
        side_effect=delayed_side_effect()
    )
    mock_flasher_manager.async_start_addon_waiting = AsyncMock(
        side_effect=delayed_side_effect()
    )
    mock_flasher_manager.async_uninstall_addon_waiting = AsyncMock(
        side_effect=delayed_side_effect()
    )

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

        # Pick the menu option: we are now installing the addon
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["progress_action"] == "install_addon"
        assert result["step_id"] == "install_zigbee_flasher_addon"

        await hass.async_block_till_done(wait_background_tasks=True)

        # Progress the flow, we are now configuring the addon and running it
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
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

        # Progress the flow, we are now uninstalling the addon
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "uninstall_zigbee_flasher_addon"
        assert result["progress_action"] == "uninstall_zigbee_flasher_addon"

        await hass.async_block_till_done(wait_background_tasks=True)

        # We are finally done with the addon
        assert mock_flasher_manager.async_uninstall_addon_waiting.mock_calls == [call()]

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm_zigbee"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
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
async def test_config_flow_zigbee_skip_step_if_installed(
    usb_data: usb.UsbServiceInfo, model: str, hass: HomeAssistant
) -> None:
    """Test the config flow for SkyConnect, skip installing the addon if necessary."""
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
        return_value=ApplicationType.SPINEL,  # Ensure we re-install it
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "pick_firmware"
    assert result["description_placeholders"]["firmware_type"] == "spinel"

    # Set up Zigbee firmware
    mock_flasher_manager = Mock(spec_set=get_zigbee_flasher_addon_manager(hass))
    mock_flasher_manager.async_start_addon_waiting = AsyncMock(
        side_effect=delayed_side_effect()
    )
    mock_flasher_manager.async_uninstall_addon_waiting = AsyncMock(
        side_effect=delayed_side_effect()
    )

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

        # Pick the menu option: we skip installation, instead we directly run it
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
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

        # Uninstall the addon
        await hass.async_block_till_done(wait_background_tasks=True)
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Done
    await hass.async_block_till_done(wait_background_tasks=True)
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm_zigbee"


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
    assert result["description_placeholders"]["firmware_type"] == "ezsp"

    # Set up Thread firmware
    mock_otbr_manager = Mock(spec_set=get_otbr_addon_manager(hass))
    mock_otbr_manager.async_install_addon_waiting = AsyncMock(
        side_effect=delayed_side_effect()
    )
    mock_otbr_manager.async_start_addon_waiting = AsyncMock(
        side_effect=delayed_side_effect()
    )

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
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

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

        # The addon is now running
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm_otbr"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.data == {
        "firmware": "spinel",
        "device": usb_data.device,
        "manufacturer": usb_data.manufacturer,
        "pid": usb_data.pid,
        "description": usb_data.description,
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
async def test_config_flow_thread_addon_already_installed(
    usb_data: usb.UsbServiceInfo, model: str, hass: HomeAssistant
) -> None:
    """Test the Thread config flow for SkyConnect, addon is already installed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "usb"}, data=usb_data
    )

    with patch(
        "homeassistant.components.homeassistant_sky_connect.config_flow.probe_silabs_firmware_type",
        return_value=ApplicationType.EZSP,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    mock_otbr_manager = Mock(spec_set=get_otbr_addon_manager(hass))
    mock_otbr_manager.addon_name = "OpenThread Border Router"
    mock_otbr_manager.async_install_addon_waiting = AsyncMock(
        side_effect=delayed_side_effect()
    )
    mock_otbr_manager.async_start_addon_waiting = AsyncMock(
        side_effect=delayed_side_effect()
    )
    mock_otbr_manager.async_get_addon_info.return_value = AddonInfo(
        available=True,
        hostname=None,
        options={},
        state=AddonState.NOT_RUNNING,
        update_available=False,
        version=None,
    )

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
        # Pick the menu option
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_THREAD},
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

        # The addon is now running
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm_otbr"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("usb_data", "model"),
    [
        (USB_DATA_ZBT1, "Home Assistant Connect ZBT-1"),
    ],
)
async def test_config_flow_zigbee_not_hassio(
    usb_data: usb.UsbServiceInfo, model: str, hass: HomeAssistant
) -> None:
    """Test when the stick is used with a non-hassio setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "usb"}, data=usb_data
    )

    with patch(
        "homeassistant.components.homeassistant_sky_connect.config_flow.probe_silabs_firmware_type",
        return_value=ApplicationType.EZSP,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    with (
        patch(
            "homeassistant.components.homeassistant_sky_connect.config_flow.is_hassio",
            return_value=False,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm_zigbee"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
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
async def test_options_flow_zigbee_to_thread(
    usb_data: usb.UsbServiceInfo, model: str, hass: HomeAssistant
) -> None:
    """Test the options flow for SkyConnect, migrating Zigbee to Thread."""
    config_entry = MockConfigEntry(
        domain="homeassistant_sky_connect",
        data={
            "firmware": "ezsp",
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
    assert result["description_placeholders"]["firmware_type"] == "ezsp"
    assert result["description_placeholders"]["model"] == model

    # Pick Thread
    mock_otbr_manager = Mock(spec_set=get_otbr_addon_manager(hass))
    mock_otbr_manager.async_install_addon_waiting = AsyncMock(
        side_effect=delayed_side_effect()
    )
    mock_otbr_manager.async_start_addon_waiting = AsyncMock(
        side_effect=delayed_side_effect()
    )

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

        result = await hass.config_entries.options.async_configure(
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
        result = await hass.config_entries.options.async_configure(result["flow_id"])

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

        # The addon is now running
        result = await hass.config_entries.options.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm_otbr"

    # We are now done
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # The firmware type has been updated
    assert config_entry.data["firmware"] == "spinel"


@pytest.mark.parametrize(
    ("usb_data", "model"),
    [
        (USB_DATA_SKY, "Home Assistant SkyConnect"),
        (USB_DATA_ZBT1, "Home Assistant Connect ZBT-1"),
    ],
)
async def test_options_flow_thread_to_zigbee(
    usb_data: usb.UsbServiceInfo, model: str, hass: HomeAssistant
) -> None:
    """Test the options flow for SkyConnect, migrating Thread to Zigbee."""
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

    # Set up Zigbee firmware
    mock_flasher_manager = Mock(spec_set=get_zigbee_flasher_addon_manager(hass))
    mock_flasher_manager.async_install_addon_waiting = AsyncMock(
        side_effect=delayed_side_effect()
    )
    mock_flasher_manager.async_start_addon_waiting = AsyncMock(
        side_effect=delayed_side_effect()
    )
    mock_flasher_manager.async_uninstall_addon_waiting = AsyncMock(
        side_effect=delayed_side_effect()
    )

    # OTBR is not installed
    mock_otbr_manager = Mock(spec_set=get_otbr_addon_manager(hass))
    mock_otbr_manager.async_get_addon_info.return_value = AddonInfo(
        available=True,
        hostname=None,
        options={},
        state=AddonState.NOT_INSTALLED,
        update_available=False,
        version=None,
    )

    with (
        patch(
            "homeassistant.components.homeassistant_sky_connect.config_flow.get_zigbee_flasher_addon_manager",
            return_value=mock_flasher_manager,
        ),
        patch(
            "homeassistant.components.homeassistant_sky_connect.config_flow.get_otbr_addon_manager",
            return_value=mock_otbr_manager,
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

        # Pick the menu option: we are now installing the addon
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["progress_action"] == "install_addon"
        assert result["step_id"] == "install_zigbee_flasher_addon"

        await hass.async_block_till_done(wait_background_tasks=True)

        # Progress the flow, we are now configuring the addon and running it
        result = await hass.config_entries.options.async_configure(result["flow_id"])
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

        # Progress the flow, we are now uninstalling the addon
        result = await hass.config_entries.options.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "uninstall_zigbee_flasher_addon"
        assert result["progress_action"] == "uninstall_zigbee_flasher_addon"

        await hass.async_block_till_done(wait_background_tasks=True)

        # We are finally done with the addon
        assert mock_flasher_manager.async_uninstall_addon_waiting.mock_calls == [call()]

        result = await hass.config_entries.options.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm_zigbee"

    # We are now done
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # The firmware type has been updated
    assert config_entry.data["firmware"] == "ezsp"


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
