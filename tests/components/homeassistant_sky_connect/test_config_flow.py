"""Test the Home Assistant SkyConnect config flow."""

from collections.abc import Generator
import copy
from unittest.mock import Mock, patch

import pytest

from homeassistant.components import homeassistant_sky_connect, usb
from homeassistant.components.homeassistant_sky_connect.const import DOMAIN
from homeassistant.components.zha import (
    CONF_DEVICE_PATH,
    DOMAIN as ZHA_DOMAIN,
    RadioType,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, MockModule, mock_integration

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


@pytest.fixture(autouse=True)
def config_flow_handler(hass: HomeAssistant) -> Generator[None, None, None]:
    """Fixture for a test config flow."""
    with patch(
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.WaitingAddonManager.async_wait_until_addon_state"
    ):
        yield


@pytest.mark.parametrize(
    ("usb_data", "title"),
    [
        (USB_DATA_SKY, "Home Assistant SkyConnect"),
        (USB_DATA_ZBT1, "Home Assistant Connect ZBT-1"),
    ],
)
async def test_config_flow(
    usb_data: usb.UsbServiceInfo, title: str, hass: HomeAssistant
) -> None:
    """Test the config flow for SkyConnect."""
    with patch(
        "homeassistant.components.homeassistant_sky_connect.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "usb"}, data=usb_data
        )

    expected_data = {
        "device": usb_data.device,
        "vid": usb_data.vid,
        "pid": usb_data.pid,
        "serial_number": usb_data.serial_number,
        "manufacturer": usb_data.manufacturer,
        "description": usb_data.description,
    }

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == title
    assert result["data"] == expected_data
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == expected_data
    assert config_entry.options == {}
    assert config_entry.title == title
    assert (
        config_entry.unique_id
        == f"{usb_data.vid}:{usb_data.pid}_{usb_data.serial_number}_{usb_data.manufacturer}_{usb_data.description}"
    )


@pytest.mark.parametrize(
    ("usb_data", "title"),
    [
        (USB_DATA_SKY, "Home Assistant SkyConnect"),
        (USB_DATA_ZBT1, "Home Assistant Connect ZBT-1"),
    ],
)
async def test_config_flow_multiple_entries(
    usb_data: usb.UsbServiceInfo, title: str, hass: HomeAssistant
) -> None:
    """Test multiple entries are allowed."""
    # Setup an existing config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title=title,
        unique_id=f"{usb_data.vid}:{usb_data.pid}_{usb_data.serial_number}_{usb_data.manufacturer}_{usb_data.description}",
    )
    config_entry.add_to_hass(hass)

    usb_data = copy.copy(usb_data)
    usb_data.serial_number = "bla_serial_number_2"

    with patch(
        "homeassistant.components.homeassistant_sky_connect.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "usb"}, data=usb_data
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("usb_data", "title"),
    [
        (USB_DATA_SKY, "Home Assistant SkyConnect"),
        (USB_DATA_ZBT1, "Home Assistant Connect ZBT-1"),
    ],
)
async def test_config_flow_update_device(
    usb_data: usb.UsbServiceInfo, title: str, hass: HomeAssistant
) -> None:
    """Test updating device path."""
    # Setup an existing config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title=title,
        unique_id=f"{usb_data.vid}:{usb_data.pid}_{usb_data.serial_number}_{usb_data.manufacturer}_{usb_data.description}",
    )
    config_entry.add_to_hass(hass)

    usb_data = copy.copy(usb_data)
    usb_data.device = "bla_device_2"

    with patch(
        "homeassistant.components.homeassistant_sky_connect.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert len(mock_setup_entry.mock_calls) == 1

    with (
        patch(
            "homeassistant.components.homeassistant_sky_connect.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.homeassistant_sky_connect.async_unload_entry",
            wraps=homeassistant_sky_connect.async_unload_entry,
        ) as mock_unload_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "usb"}, data=usb_data
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_unload_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("usb_data", "title"),
    [
        (USB_DATA_SKY, "Home Assistant SkyConnect"),
        (USB_DATA_ZBT1, "Home Assistant ZBT-1"),
    ],
)
async def test_option_flow_install_multi_pan_addon(
    usb_data: usb.UsbServiceInfo,
    title: str,
    hass: HomeAssistant,
    addon_store_info,
    addon_info,
    install_addon,
    set_addon_options,
    start_addon,
) -> None:
    """Test installing the multi pan addon."""
    assert await async_setup_component(hass, "usb", {})
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={
            "device": usb_data.device,
            "vid": usb_data.vid,
            "pid": usb_data.pid,
            "serial_number": usb_data.serial_number,
            "manufacturer": usb_data.manufacturer,
            "description": usb_data.description,
        },
        domain=DOMAIN,
        options={},
        title=title,
        unique_id=f"{usb_data.vid}:{usb_data.pid}_{usb_data.serial_number}_{usb_data.manufacturer}_{usb_data.description}",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.is_hassio",
        side_effect=Mock(return_value=True),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "addon_not_installed"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "enable_multi_pan": True,
        },
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "install_addon"
    assert result["progress_action"] == "install_addon"

    await hass.async_block_till_done()
    install_addon.assert_called_once_with(hass, "core_silabs_multiprotocol")

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"
    set_addon_options.assert_called_once_with(
        hass,
        "core_silabs_multiprotocol",
        {
            "options": {
                "autoflash_firmware": True,
                "device": usb_data.device,
                "baudrate": "115200",
                "flow_control": True,
            }
        },
    )

    await hass.async_block_till_done()
    start_addon.assert_called_once_with(hass, "core_silabs_multiprotocol")

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY


def mock_detect_radio_type(radio_type=RadioType.ezsp, ret=True):
    """Mock `detect_radio_type` that just sets the appropriate attributes."""

    async def detect(self):
        self.radio_type = radio_type
        self.device_settings = radio_type.controller.SCHEMA_DEVICE(
            {CONF_DEVICE_PATH: self.device_path}
        )

        return ret

    return detect


@pytest.mark.parametrize(
    ("usb_data", "title"),
    [
        (USB_DATA_SKY, "Home Assistant SkyConnect"),
        (USB_DATA_ZBT1, "Home Assistant Connect ZBT-1"),
    ],
)
@patch(
    "homeassistant.components.zha.radio_manager.ZhaRadioManager.detect_radio_type",
    mock_detect_radio_type(),
)
async def test_option_flow_install_multi_pan_addon_zha(
    usb_data: usb.UsbServiceInfo,
    title: str,
    hass: HomeAssistant,
    addon_store_info,
    addon_info,
    install_addon,
    set_addon_options,
    start_addon,
) -> None:
    """Test installing the multi pan addon when a zha config entry exists."""
    assert await async_setup_component(hass, "usb", {})
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={
            "device": usb_data.device,
            "vid": usb_data.vid,
            "pid": usb_data.pid,
            "serial_number": usb_data.serial_number,
            "manufacturer": usb_data.manufacturer,
            "description": usb_data.description,
        },
        domain=DOMAIN,
        options={},
        title=title,
        unique_id=f"{usb_data.vid}:{usb_data.pid}_{usb_data.serial_number}_{usb_data.manufacturer}_{usb_data.description}",
    )
    config_entry.add_to_hass(hass)

    zha_config_entry = MockConfigEntry(
        data={"device": {"path": usb_data.device}, "radio_type": "ezsp"},
        domain=ZHA_DOMAIN,
        options={},
        title="Yellow",
    )
    zha_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.is_hassio",
        side_effect=Mock(return_value=True),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "addon_not_installed"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "enable_multi_pan": True,
        },
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "install_addon"
    assert result["progress_action"] == "install_addon"

    await hass.async_block_till_done()
    install_addon.assert_called_once_with(hass, "core_silabs_multiprotocol")

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"
    set_addon_options.assert_called_once_with(
        hass,
        "core_silabs_multiprotocol",
        {
            "options": {
                "autoflash_firmware": True,
                "device": usb_data.device,
                "baudrate": "115200",
                "flow_control": True,
            }
        },
    )
    # Check the ZHA config entry data is updated
    assert zha_config_entry.data == {
        "device": {
            "path": "socket://core-silabs-multiprotocol:9999",
            "baudrate": 115200,
            "flow_control": None,
        },
        "radio_type": "ezsp",
    }

    await hass.async_block_till_done()
    start_addon.assert_called_once_with(hass, "core_silabs_multiprotocol")

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY
