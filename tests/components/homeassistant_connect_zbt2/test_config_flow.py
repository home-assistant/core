"""Test the Home Assistant Connect ZBT-2 config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, call, patch

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


@pytest.fixture(name="supervisor")
def mock_supervisor_fixture() -> Generator[None]:
    """Mock Supervisor."""
    with patch(
        "homeassistant.components.homeassistant_hardware.firmware_config_flow.is_hassio",
        return_value=True,
    ):
        yield


@pytest.fixture(name="setup_entry", autouse=True)
def setup_entry_fixture() -> Generator[AsyncMock]:
    """Mock entry setup."""
    with patch(
        "homeassistant.components.homeassistant_connect_zbt2.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


async def test_config_flow_zigbee(
    hass: HomeAssistant,
) -> None:
    """Test Zigbee config flow for Connect ZBT-2."""
    fw_type = ApplicationType.EZSP
    fw_version = "7.4.4.0 build 0"
    model = "Home Assistant Connect ZBT-2"
    usb_data = USB_DATA_ZBT2

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "usb"}, data=usb_data
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "pick_firmware"
    description_placeholders = result["description_placeholders"]
    assert description_placeholders is not None
    assert description_placeholders["model"] == model

    async def mock_install_firmware_step(
        self,
        fw_update_url: str,
        fw_type: str,
        firmware_name: str,
        expected_installed_firmware_type: ApplicationType,
        step_id: str,
        next_step_id: str,
    ) -> ConfigFlowResult:
        return await getattr(self, f"async_step_{next_step_id}")()

    with (
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
        pick_result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )

        assert pick_result["type"] is FlowResultType.MENU
        assert pick_result["step_id"] == "zigbee_installation_type"

        create_result = await hass.config_entries.flow.async_configure(
            pick_result["flow_id"],
            user_input={"next_step_id": "zigbee_intent_recommended"},
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

    # Ensure a ZHA discovery flow has been created
    assert len(flows) == 1
    zha_flow = flows[0]
    assert zha_flow["handler"] == "zha"
    assert zha_flow["context"]["source"] == "hardware"
    assert zha_flow["step_id"] == "confirm"


@pytest.mark.usefixtures("addon_installed", "supervisor")
async def test_config_flow_thread(
    hass: HomeAssistant,
    start_addon: AsyncMock,
) -> None:
    """Test Thread config flow for Connect ZBT-2."""
    fw_type = ApplicationType.SPINEL
    fw_version = "2.4.4.0"
    model = "Home Assistant Connect ZBT-2"
    usb_data = USB_DATA_ZBT2

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "usb"}, data=usb_data
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "pick_firmware"
    description_placeholders = result["description_placeholders"]
    assert description_placeholders is not None
    assert description_placeholders["model"] == model

    async def mock_install_firmware_step(
        self,
        fw_update_url: str,
        fw_type: str,
        firmware_name: str,
        expected_installed_firmware_type: ApplicationType,
        step_id: str,
        next_step_id: str,
    ) -> ConfigFlowResult:
        return await getattr(self, f"async_step_{next_step_id}")()

    with (
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
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_THREAD},
        )

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "start_otbr_addon"

        # Make sure the flow continues when the progress task is done.
        await hass.async_block_till_done()

        create_result = await hass.config_entries.flow.async_configure(
            result["flow_id"]
        )

    assert start_addon.call_count == 1
    assert start_addon.call_args == call("core_openthread_border_router")
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
    description_placeholders = result["description_placeholders"]
    assert description_placeholders is not None
    assert description_placeholders["firmware_type"] == "spinel"
    assert description_placeholders["model"] == model

    mock_update_client = AsyncMock()
    mock_manifest = Mock()
    mock_firmware = Mock()
    mock_firmware.filename = "zbt2_zigbee_ncp_7.4.4.0.gbl"
    mock_firmware.metadata = {
        "ezsp_version": "7.4.4.0",
        "fw_type": "zbt2_zigbee_ncp",
        "metadata_version": 2,
    }
    mock_manifest.firmwares = [mock_firmware]
    mock_update_client.async_update_data.return_value = mock_manifest
    mock_update_client.async_fetch_firmware.return_value = b"firmware_data"

    with (
        patch(
            "homeassistant.components.homeassistant_hardware.firmware_config_flow.guess_hardware_owners",
            return_value=[],
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.firmware_config_flow.FirmwareUpdateClient",
            return_value=mock_update_client,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.firmware_config_flow.async_flash_silabs_firmware",
            return_value=FirmwareInfo(
                device=usb_data.device,
                firmware_type=ApplicationType.EZSP,
                firmware_version="7.4.4.0 build 0",
                owners=[],
                source="probe",
            ),
        ) as flash_mock,
        patch(
            "homeassistant.components.homeassistant_hardware.firmware_config_flow.probe_silabs_firmware_info",
            side_effect=[
                # First call: probe before installation (returns current SPINEL firmware)
                FirmwareInfo(
                    device=usb_data.device,
                    firmware_type=ApplicationType.SPINEL,
                    firmware_version="2.4.4.0",
                    owners=[],
                    source="probe",
                ),
                # Second call: probe after installation (returns new EZSP firmware)
                FirmwareInfo(
                    device=usb_data.device,
                    firmware_type=ApplicationType.EZSP,
                    firmware_version="7.4.4.0 build 0",
                    owners=[],
                    source="probe",
                ),
            ],
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.util.parse_firmware_image"
        ),
    ):
        pick_result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )

        assert pick_result["type"] is FlowResultType.MENU
        assert pick_result["step_id"] == "zigbee_installation_type"

        create_result = await hass.config_entries.options.async_configure(
            pick_result["flow_id"],
            user_input={"next_step_id": "zigbee_intent_recommended"},
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

    # Verify async_flash_silabs_firmware was called with ZBT-2's reset methods
    assert flash_mock.call_count == 1
    assert flash_mock.mock_calls[0].kwargs["bootloader_reset_type"] == (
        "rts_dtr",
        "baudrate",
    )


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
