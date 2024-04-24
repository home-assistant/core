"""Test the Home Assistant SkyConnect config flow."""
from collections.abc import Generator
import copy
from unittest.mock import Mock, patch

import pytest

from homeassistant.components import homeassistant_sky_connect, usb
from homeassistant.components.homeassistant_sky_connect.const import DOMAIN
from homeassistant.components.zha.core.const import (
    CONF_DEVICE_PATH,
    DOMAIN as ZHA_DOMAIN,
    RadioType,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, MockModule, mock_integration

USB_DATA = usb.UsbServiceInfo(
    device="bla_device",
    vid="bla_vid",
    pid="bla_pid",
    serial_number="bla_serial_number",
    manufacturer="bla_manufacturer",
    description="bla_description",
)


@pytest.fixture(autouse=True)
def config_flow_handler(hass: HomeAssistant) -> Generator[None, None, None]:
    """Fixture for a test config flow."""
    with patch(
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.WaitingAddonManager.async_wait_until_addon_state"
    ):
        yield


async def test_config_flow(hass: HomeAssistant) -> None:
    """Test the config flow."""
    with patch(
        "homeassistant.components.homeassistant_sky_connect.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "usb"}, data=USB_DATA
        )

    expected_data = {
        "device": USB_DATA.device,
        "vid": USB_DATA.vid,
        "pid": USB_DATA.pid,
        "serial_number": USB_DATA.serial_number,
        "manufacturer": USB_DATA.manufacturer,
        "description": USB_DATA.description,
    }

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home Assistant SkyConnect"
    assert result["data"] == expected_data
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == expected_data
    assert config_entry.options == {}
    assert config_entry.title == "Home Assistant SkyConnect"
    assert (
        config_entry.unique_id
        == f"{USB_DATA.vid}:{USB_DATA.pid}_{USB_DATA.serial_number}_{USB_DATA.manufacturer}_{USB_DATA.description}"
    )


async def test_config_flow_unique_id(hass: HomeAssistant) -> None:
    """Test only a single entry is allowed for a dongle."""
    # Setup an existing config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant SkyConnect",
        unique_id=f"{USB_DATA.vid}:{USB_DATA.pid}_{USB_DATA.serial_number}_{USB_DATA.manufacturer}_{USB_DATA.description}",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_sky_connect.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "usb"}, data=USB_DATA
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_setup_entry.assert_not_called()


async def test_config_flow_multiple_entries(hass: HomeAssistant) -> None:
    """Test multiple entries are allowed."""
    # Setup an existing config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant SkyConnect",
        unique_id=f"{USB_DATA.vid}:{USB_DATA.pid}_{USB_DATA.serial_number}_{USB_DATA.manufacturer}_{USB_DATA.description}",
    )
    config_entry.add_to_hass(hass)

    usb_data = copy.copy(USB_DATA)
    usb_data.serial_number = "bla_serial_number_2"

    with patch(
        "homeassistant.components.homeassistant_sky_connect.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "usb"}, data=usb_data
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_config_flow_update_device(hass: HomeAssistant) -> None:
    """Test updating device path."""
    # Setup an existing config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant SkyConnect",
        unique_id=f"{USB_DATA.vid}:{USB_DATA.pid}_{USB_DATA.serial_number}_{USB_DATA.manufacturer}_{USB_DATA.description}",
    )
    config_entry.add_to_hass(hass)

    usb_data = copy.copy(USB_DATA)
    usb_data.device = "bla_device_2"

    with patch(
        "homeassistant.components.homeassistant_sky_connect.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert len(mock_setup_entry.mock_calls) == 1

    with patch(
        "homeassistant.components.homeassistant_sky_connect.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.homeassistant_sky_connect.async_unload_entry",
        wraps=homeassistant_sky_connect.async_unload_entry,
    ) as mock_unload_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "usb"}, data=usb_data
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_unload_entry.mock_calls) == 1


async def test_option_flow_install_multi_pan_addon(
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
            "device": USB_DATA.device,
            "vid": USB_DATA.vid,
            "pid": USB_DATA.pid,
            "serial_number": USB_DATA.serial_number,
            "manufacturer": USB_DATA.manufacturer,
            "description": USB_DATA.description,
        },
        domain=DOMAIN,
        options={},
        title="Home Assistant SkyConnect",
        unique_id=f"{USB_DATA.vid}:{USB_DATA.pid}_{USB_DATA.serial_number}_{USB_DATA.manufacturer}_{USB_DATA.description}",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon.is_hassio",
        side_effect=Mock(return_value=True),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "addon_not_installed"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "enable_multi_pan": True,
        },
    )
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "install_addon"
    assert result["progress_action"] == "install_addon"

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "configure_addon"
    install_addon.assert_called_once_with(hass, "core_silabs_multiprotocol")

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"
    set_addon_options.assert_called_once_with(
        hass,
        "core_silabs_multiprotocol",
        {
            "options": {
                "autoflash_firmware": True,
                "device": "bla_device",
                "baudrate": "115200",
                "flow_control": True,
            }
        },
    )

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "finish_addon_setup"
    start_addon.assert_called_once_with(hass, "core_silabs_multiprotocol")

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.CREATE_ENTRY


def mock_detect_radio_type(radio_type=RadioType.ezsp, ret=True):
    """Mock `detect_radio_type` that just sets the appropriate attributes."""

    async def detect(self):
        self.radio_type = radio_type
        self.device_settings = radio_type.controller.SCHEMA_DEVICE(
            {CONF_DEVICE_PATH: self.device_path}
        )

        return ret

    return detect


@patch(
    "homeassistant.components.zha.radio_manager.ZhaRadioManager.detect_radio_type",
    mock_detect_radio_type(),
)
async def test_option_flow_install_multi_pan_addon_zha(
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
            "device": USB_DATA.device,
            "vid": USB_DATA.vid,
            "pid": USB_DATA.pid,
            "serial_number": USB_DATA.serial_number,
            "manufacturer": USB_DATA.manufacturer,
            "description": USB_DATA.description,
        },
        domain=DOMAIN,
        options={},
        title="Home Assistant SkyConnect",
        unique_id=f"{USB_DATA.vid}:{USB_DATA.pid}_{USB_DATA.serial_number}_{USB_DATA.manufacturer}_{USB_DATA.description}",
    )
    config_entry.add_to_hass(hass)

    zha_config_entry = MockConfigEntry(
        data={"device": {"path": "bla_device"}, "radio_type": "ezsp"},
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
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "addon_not_installed"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "enable_multi_pan": True,
        },
    )
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "install_addon"
    assert result["progress_action"] == "install_addon"

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "configure_addon"
    install_addon.assert_called_once_with(hass, "core_silabs_multiprotocol")

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_addon"
    set_addon_options.assert_called_once_with(
        hass,
        "core_silabs_multiprotocol",
        {
            "options": {
                "autoflash_firmware": True,
                "device": "bla_device",
                "baudrate": "115200",
                "flow_control": True,
            }
        },
    )
    # Check the ZHA config entry data is updated
    assert zha_config_entry.data == {
        "device": {
            "path": "socket://core-silabs-multiprotocol:9999",
            "baudrate": 57600,  # ZHA default
            "flow_control": "software",  # ZHA default
        },
        "radio_type": "ezsp",
    }

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "finish_addon_setup"
    start_addon.assert_called_once_with(hass, "core_silabs_multiprotocol")

    result = await hass.config_entries.options.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.CREATE_ENTRY
