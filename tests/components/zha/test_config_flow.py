"""Tests for ZHA config flow."""
import copy
from datetime import timedelta
import json
from unittest.mock import AsyncMock, MagicMock, PropertyMock, create_autospec, patch
import uuid

import pytest
import serial.tools.list_ports
from zigpy.backups import BackupManager
import zigpy.config
from zigpy.config import CONF_DEVICE, CONF_DEVICE_PATH
from zigpy.exceptions import NetworkNotFormed
import zigpy.types

from homeassistant import config_entries
from homeassistant.components import ssdp, usb, zeroconf
from homeassistant.components.hassio import AddonState
from homeassistant.components.ssdp import ATTR_UPNP_MANUFACTURER_URL, ATTR_UPNP_SERIAL
from homeassistant.components.zha import config_flow, radio_manager
from homeassistant.components.zha.core.const import (
    CONF_BAUDRATE,
    CONF_FLOWCONTROL,
    CONF_RADIO_TYPE,
    DOMAIN,
    EZSP_OVERWRITE_EUI64,
    RadioType,
)
from homeassistant.config_entries import (
    SOURCE_SSDP,
    SOURCE_USB,
    SOURCE_USER,
    SOURCE_ZEROCONF,
)
from homeassistant.const import CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

PROBE_FUNCTION_PATH = "zigbee.application.ControllerApplication.probe"


@pytest.fixture(autouse=True)
def disable_platform_only():
    """Disable platforms to speed up tests."""
    with patch("homeassistant.components.zha.PLATFORMS", []):
        yield


@pytest.fixture(autouse=True)
def reduce_reconnect_timeout():
    """Reduces reconnect timeout to speed up tests."""
    with patch("homeassistant.components.zha.radio_manager.CONNECT_DELAY_S", 0.01):
        yield


@pytest.fixture(autouse=True)
def mock_app():
    """Mock zigpy app interface."""
    mock_app = AsyncMock()
    mock_app.backups = create_autospec(BackupManager, instance=True)
    mock_app.backups.backups = []

    with patch(
        "zigpy.application.ControllerApplication.new", AsyncMock(return_value=mock_app)
    ):
        yield mock_app


@pytest.fixture
def make_backup():
    """Zigpy network backup factory that creates unique backups with each call."""
    num_calls = 0

    def inner(*, backup_time_offset=0):
        nonlocal num_calls

        backup = zigpy.backups.NetworkBackup()
        backup.backup_time += timedelta(seconds=backup_time_offset)
        backup.node_info.ieee = zigpy.types.EUI64.convert(f"AABBCCDDEE{num_calls:06X}")
        num_calls += 1

        return backup

    return inner


@pytest.fixture
def backup(make_backup):
    """Zigpy network backup with non-default settings."""
    return make_backup()


def mock_detect_radio_type(radio_type=RadioType.ezsp, ret=True):
    """Mock `detect_radio_type` that just sets the appropriate attributes."""

    async def detect(self):
        self.radio_type = radio_type
        self.device_settings = radio_type.controller.SCHEMA_DEVICE(
            {CONF_DEVICE_PATH: self.device_path}
        )

        return ret

    return detect


def com_port(device="/dev/ttyUSB1234"):
    """Mock of a serial port."""
    port = serial.tools.list_ports_common.ListPortInfo("/dev/ttyUSB1234")
    port.serial_number = "1234"
    port.manufacturer = "Virtual serial port"
    port.device = device
    port.description = "Some serial port"

    return port


@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
@patch(f"zigpy_znp.{PROBE_FUNCTION_PATH}", AsyncMock(return_value=True))
async def test_zeroconf_discovery_znp(hass: HomeAssistant) -> None:
    """Test zeroconf flow -- radio detected."""
    service_info = zeroconf.ZeroconfServiceInfo(
        host="192.168.1.200",
        addresses=["192.168.1.200"],
        hostname="tube._tube_zb_gw._tcp.local.",
        name="tube",
        port=6053,
        properties={"name": "tube_123456"},
        type="mock_type",
    )
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=service_info
    )
    assert flow["step_id"] == "confirm"

    # Confirm discovery
    result1 = await hass.config_entries.flow.async_configure(
        flow["flow_id"], user_input={}
    )
    assert result1["step_id"] == "manual_port_config"

    # Confirm port settings
    result2 = await hass.config_entries.flow.async_configure(
        result1["flow_id"], user_input={}
    )

    assert result2["type"] == FlowResultType.MENU
    assert result2["step_id"] == "choose_formation_strategy"

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={"next_step_id": config_flow.FORMATION_REUSE_SETTINGS},
    )
    await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "socket://192.168.1.200:6638"
    assert result3["data"] == {
        CONF_DEVICE: {
            CONF_BAUDRATE: 115200,
            CONF_FLOWCONTROL: None,
            CONF_DEVICE_PATH: "socket://192.168.1.200:6638",
        },
        CONF_RADIO_TYPE: "znp",
    }


@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
@patch(f"zigpy_zigate.{PROBE_FUNCTION_PATH}")
async def test_zigate_via_zeroconf(setup_entry_mock, hass: HomeAssistant) -> None:
    """Test zeroconf flow -- zigate radio detected."""
    service_info = zeroconf.ZeroconfServiceInfo(
        host="192.168.1.200",
        addresses=["192.168.1.200"],
        hostname="_zigate-zigbee-gateway._tcp.local.",
        name="any",
        port=1234,
        properties={"radio_type": "zigate"},
        type="mock_type",
    )
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=service_info
    )
    assert flow["step_id"] == "confirm"

    # Confirm discovery
    result1 = await hass.config_entries.flow.async_configure(
        flow["flow_id"], user_input={}
    )
    assert result1["step_id"] == "manual_port_config"

    # Confirm the radio is deprecated
    result2 = await hass.config_entries.flow.async_configure(
        flow["flow_id"], user_input={}
    )
    assert result2["step_id"] == "verify_radio"
    assert "ZiGate" in result2["description_placeholders"]["name"]

    # Confirm port settings
    result3 = await hass.config_entries.flow.async_configure(
        result1["flow_id"], user_input={}
    )

    assert result3["type"] == FlowResultType.MENU
    assert result3["step_id"] == "choose_formation_strategy"

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        user_input={"next_step_id": config_flow.FORMATION_REUSE_SETTINGS},
    )
    await hass.async_block_till_done()

    assert result4["type"] == FlowResultType.CREATE_ENTRY
    assert result4["title"] == "socket://192.168.1.200:1234"
    assert result4["data"] == {
        CONF_DEVICE: {
            CONF_DEVICE_PATH: "socket://192.168.1.200:1234",
        },
        CONF_RADIO_TYPE: "zigate",
    }


@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
@patch(f"bellows.{PROBE_FUNCTION_PATH}", AsyncMock(return_value=True))
async def test_efr32_via_zeroconf(hass: HomeAssistant) -> None:
    """Test zeroconf flow -- efr32 radio detected."""
    service_info = zeroconf.ZeroconfServiceInfo(
        host="192.168.1.200",
        addresses=["192.168.1.200"],
        hostname="efr32._esphomelib._tcp.local.",
        name="efr32",
        port=1234,
        properties={},
        type="mock_type",
    )
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=service_info
    )
    assert flow["step_id"] == "confirm"

    # Confirm discovery
    result1 = await hass.config_entries.flow.async_configure(
        flow["flow_id"], user_input={}
    )
    assert result1["step_id"] == "manual_port_config"

    # Confirm port settings
    result2 = await hass.config_entries.flow.async_configure(
        result1["flow_id"], user_input={}
    )

    assert result2["type"] == FlowResultType.MENU
    assert result2["step_id"] == "choose_formation_strategy"

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={"next_step_id": config_flow.FORMATION_REUSE_SETTINGS},
    )
    await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "socket://192.168.1.200:1234"
    assert result3["data"] == {
        CONF_DEVICE: {
            CONF_DEVICE_PATH: "socket://192.168.1.200:1234",
            CONF_BAUDRATE: 115200,
            CONF_FLOWCONTROL: "software",
        },
        CONF_RADIO_TYPE: "ezsp",
    }


@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
@patch(f"zigpy_znp.{PROBE_FUNCTION_PATH}", AsyncMock(return_value=True))
async def test_discovery_via_zeroconf_ip_change(hass: HomeAssistant) -> None:
    """Test zeroconf flow -- radio detected."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="tube_zb_gw_cc2652p2_poe",
        data={
            CONF_DEVICE: {
                CONF_DEVICE_PATH: "socket://192.168.1.5:6638",
                CONF_BAUDRATE: 115200,
                CONF_FLOWCONTROL: None,
            }
        },
    )
    entry.add_to_hass(hass)

    service_info = zeroconf.ZeroconfServiceInfo(
        host="192.168.1.22",
        addresses=["192.168.1.22"],
        hostname="tube_zb_gw_cc2652p2_poe.local.",
        name="mock_name",
        port=6053,
        properties={"address": "tube_zb_gw_cc2652p2_poe.local"},
        type="mock_type",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=service_info
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_DEVICE] == {
        CONF_DEVICE_PATH: "socket://192.168.1.22:6638",
        CONF_BAUDRATE: 115200,
        CONF_FLOWCONTROL: None,
    }


@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
@patch(f"zigpy_znp.{PROBE_FUNCTION_PATH}", AsyncMock(return_value=True))
async def test_discovery_via_zeroconf_ip_change_ignored(hass: HomeAssistant) -> None:
    """Test zeroconf flow that was ignored gets updated."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="tube_zb_gw_cc2652p2_poe",
        source=config_entries.SOURCE_IGNORE,
    )
    entry.add_to_hass(hass)

    service_info = zeroconf.ZeroconfServiceInfo(
        host="192.168.1.22",
        addresses=["192.168.1.22"],
        hostname="tube_zb_gw_cc2652p2_poe.local.",
        name="mock_name",
        port=6053,
        properties={"address": "tube_zb_gw_cc2652p2_poe.local"},
        type="mock_type",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=service_info
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_DEVICE] == {
        CONF_DEVICE_PATH: "socket://192.168.1.22:6638",
    }


async def test_discovery_confirm_final_abort_if_entries(hass: HomeAssistant) -> None:
    """Test discovery aborts if ZHA was set up after the confirmation dialog is shown."""
    service_info = zeroconf.ZeroconfServiceInfo(
        host="192.168.1.200",
        addresses=["192.168.1.200"],
        hostname="tube._tube_zb_gw._tcp.local.",
        name="tube",
        port=6053,
        properties={"name": "tube_123456"},
        type="mock_type",
    )
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=service_info
    )
    assert flow["step_id"] == "confirm"

    # ZHA was somehow set up while we were in the config flow
    with patch(
        "homeassistant.config_entries.ConfigFlow._async_current_entries",
        return_value=[MagicMock()],
    ):
        # Confirm discovery
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], user_input={}
        )

    # Config will fail
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@patch(f"zigpy_znp.{PROBE_FUNCTION_PATH}", AsyncMock(return_value=True))
async def test_discovery_via_usb(hass: HomeAssistant) -> None:
    """Test usb flow -- radio detected."""
    discovery_info = usb.UsbServiceInfo(
        device="/dev/ttyZIGBEE",
        pid="AAAA",
        vid="AAAA",
        serial_number="1234",
        description="zigbee radio",
        manufacturer="test",
    )
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USB}, data=discovery_info
    )
    await hass.async_block_till_done()

    assert result1["type"] == FlowResultType.FORM
    assert result1["step_id"] == "confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result1["flow_id"], user_input={}
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.MENU
    assert result2["step_id"] == "choose_formation_strategy"

    with patch("homeassistant.components.zha.async_setup_entry", return_value=True):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            user_input={"next_step_id": config_flow.FORMATION_REUSE_SETTINGS},
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "zigbee radio"
    assert result3["data"] == {
        "device": {
            "baudrate": 115200,
            "flow_control": None,
            "path": "/dev/ttyZIGBEE",
        },
        CONF_RADIO_TYPE: "znp",
    }


@patch(f"zigpy_zigate.{PROBE_FUNCTION_PATH}", return_value=True)
async def test_zigate_discovery_via_usb(probe_mock, hass: HomeAssistant) -> None:
    """Test zigate usb flow -- radio detected."""
    discovery_info = usb.UsbServiceInfo(
        device="/dev/ttyZIGBEE",
        pid="0403",
        vid="6015",
        serial_number="1234",
        description="zigate radio",
        manufacturer="test",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USB}, data=discovery_info
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result2["step_id"] == "verify_radio"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.MENU
    assert result3["step_id"] == "choose_formation_strategy"

    with patch("homeassistant.components.zha.async_setup_entry", return_value=True):
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            user_input={"next_step_id": config_flow.FORMATION_REUSE_SETTINGS},
        )
        await hass.async_block_till_done()

    assert result4["type"] == FlowResultType.CREATE_ENTRY
    assert result4["title"] == "zigate radio"
    assert result4["data"] == {
        "device": {
            "path": "/dev/ttyZIGBEE",
        },
        CONF_RADIO_TYPE: "zigate",
    }


@patch(f"bellows.{PROBE_FUNCTION_PATH}", return_value=False)
async def test_discovery_via_usb_no_radio(probe_mock, hass: HomeAssistant) -> None:
    """Test usb flow -- no radio detected."""
    discovery_info = usb.UsbServiceInfo(
        device="/dev/null",
        pid="AAAA",
        vid="AAAA",
        serial_number="1234",
        description="zigbee radio",
        manufacturer="test",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USB}, data=discovery_info
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    with patch("homeassistant.components.zha.async_setup_entry", return_value=True):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "usb_probe_failed"


@patch(f"zigpy_znp.{PROBE_FUNCTION_PATH}", AsyncMock(return_value=True))
async def test_discovery_via_usb_already_setup(hass: HomeAssistant) -> None:
    """Test usb flow -- already setup."""

    MockConfigEntry(
        domain=DOMAIN, data={CONF_DEVICE: {CONF_DEVICE_PATH: "/dev/ttyUSB1"}}
    ).add_to_hass(hass)

    discovery_info = usb.UsbServiceInfo(
        device="/dev/ttyZIGBEE",
        pid="AAAA",
        vid="AAAA",
        serial_number="1234",
        description="zigbee radio",
        manufacturer="test",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USB}, data=discovery_info
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
async def test_discovery_via_usb_path_changes(hass: HomeAssistant) -> None:
    """Test usb flow already setup and the path changes."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="AAAA:AAAA_1234_test_zigbee radio",
        data={
            CONF_DEVICE: {
                CONF_DEVICE_PATH: "/dev/ttyUSB1",
                CONF_BAUDRATE: 115200,
                CONF_FLOWCONTROL: None,
            }
        },
    )
    entry.add_to_hass(hass)

    discovery_info = usb.UsbServiceInfo(
        device="/dev/ttyZIGBEE",
        pid="AAAA",
        vid="AAAA",
        serial_number="1234",
        description="zigbee radio",
        manufacturer="test",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USB}, data=discovery_info
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_DEVICE] == {
        CONF_DEVICE_PATH: "/dev/ttyZIGBEE",
        CONF_BAUDRATE: 115200,
        CONF_FLOWCONTROL: None,
    }


@patch(f"zigpy_znp.{PROBE_FUNCTION_PATH}", AsyncMock(return_value=True))
async def test_discovery_via_usb_deconz_already_discovered(hass: HomeAssistant) -> None:
    """Test usb flow -- deconz discovered."""
    result = await hass.config_entries.flow.async_init(
        "deconz",
        data=ssdp.SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location="http://1.2.3.4:80/",
            upnp={
                ATTR_UPNP_MANUFACTURER_URL: "http://www.dresden-elektronik.de",
                ATTR_UPNP_SERIAL: "0000000000000000",
            },
        ),
        context={"source": SOURCE_SSDP},
    )
    await hass.async_block_till_done()
    discovery_info = usb.UsbServiceInfo(
        device="/dev/ttyZIGBEE",
        pid="AAAA",
        vid="AAAA",
        serial_number="1234",
        description="zigbee radio",
        manufacturer="test",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USB}, data=discovery_info
    )
    await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "not_zha_device"


@patch(f"zigpy_znp.{PROBE_FUNCTION_PATH}", AsyncMock(return_value=True))
async def test_discovery_via_usb_deconz_already_setup(hass: HomeAssistant) -> None:
    """Test usb flow -- deconz setup."""
    MockConfigEntry(domain="deconz", data={}).add_to_hass(hass)
    await hass.async_block_till_done()
    discovery_info = usb.UsbServiceInfo(
        device="/dev/ttyZIGBEE",
        pid="AAAA",
        vid="AAAA",
        serial_number="1234",
        description="zigbee radio",
        manufacturer="test",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USB}, data=discovery_info
    )
    await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "not_zha_device"


@patch(f"zigpy_znp.{PROBE_FUNCTION_PATH}", AsyncMock(return_value=True))
async def test_discovery_via_usb_deconz_ignored(hass: HomeAssistant) -> None:
    """Test usb flow -- deconz ignored."""
    MockConfigEntry(
        domain="deconz", source=config_entries.SOURCE_IGNORE, data={}
    ).add_to_hass(hass)
    await hass.async_block_till_done()
    discovery_info = usb.UsbServiceInfo(
        device="/dev/ttyZIGBEE",
        pid="AAAA",
        vid="AAAA",
        serial_number="1234",
        description="zigbee radio",
        manufacturer="test",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USB}, data=discovery_info
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"


@patch(f"zigpy_znp.{PROBE_FUNCTION_PATH}", AsyncMock(return_value=True))
async def test_discovery_via_usb_zha_ignored_updates(hass: HomeAssistant) -> None:
    """Test usb flow that was ignored gets updated."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=config_entries.SOURCE_IGNORE,
        data={},
        unique_id="AAAA:AAAA_1234_test_zigbee radio",
    )
    entry.add_to_hass(hass)
    await hass.async_block_till_done()
    discovery_info = usb.UsbServiceInfo(
        device="/dev/ttyZIGBEE",
        pid="AAAA",
        vid="AAAA",
        serial_number="1234",
        description="zigbee radio",
        manufacturer="test",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USB}, data=discovery_info
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_DEVICE] == {
        CONF_DEVICE_PATH: "/dev/ttyZIGBEE",
    }


@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
@patch(f"zigpy_znp.{PROBE_FUNCTION_PATH}", AsyncMock(return_value=True))
async def test_discovery_already_setup(hass: HomeAssistant) -> None:
    """Test zeroconf flow -- radio detected."""
    service_info = zeroconf.ZeroconfServiceInfo(
        host="192.168.1.200",
        addresses=["192.168.1.200"],
        hostname="_tube_zb_gw._tcp.local.",
        name="mock_name",
        port=6053,
        properties={"name": "tube_123456"},
        type="mock_type",
    )

    MockConfigEntry(
        domain=DOMAIN, data={CONF_DEVICE: {CONF_DEVICE_PATH: "/dev/ttyUSB1"}}
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=service_info
    )
    await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"


@patch(
    "homeassistant.components.zha.radio_manager.ZhaRadioManager.detect_radio_type",
    mock_detect_radio_type(radio_type=RadioType.deconz),
)
@patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
async def test_user_flow(hass: HomeAssistant) -> None:
    """Test user flow -- radio detected."""

    port = com_port()
    port_select = f"{port}, s/n: {port.serial_number} - {port.manufacturer}"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={
            zigpy.config.CONF_DEVICE_PATH: port_select,
        },
    )
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "choose_formation_strategy"

    with patch("homeassistant.components.zha.async_setup_entry", return_value=True):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": config_flow.FORMATION_REUSE_SETTINGS},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"].startswith(port.description)
    assert result2["data"] == {
        "device": {
            "path": port.device,
        },
        CONF_RADIO_TYPE: "deconz",
    }


@patch(
    "homeassistant.components.zha.radio_manager.ZhaRadioManager.detect_radio_type",
    mock_detect_radio_type(ret=False),
)
@patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
async def test_user_flow_not_detected(hass: HomeAssistant) -> None:
    """Test user flow, radio not detected."""

    port = com_port()
    port_select = f"{port}, s/n: {port.serial_number} - {port.manufacturer}"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={zigpy.config.CONF_DEVICE_PATH: port_select},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "manual_pick_radio_type"


@patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
async def test_user_flow_show_form(hass: HomeAssistant) -> None:
    """Test user step form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "choose_serial_port"


@patch("serial.tools.list_ports.comports", MagicMock(return_value=[]))
async def test_user_flow_show_manual(hass: HomeAssistant) -> None:
    """Test user flow manual entry when no comport detected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "manual_pick_radio_type"


async def test_user_flow_manual(hass: HomeAssistant) -> None:
    """Test user flow manual entry."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={zigpy.config.CONF_DEVICE_PATH: config_flow.CONF_MANUAL_PATH},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "manual_pick_radio_type"


@pytest.mark.parametrize("radio_type", RadioType.list())
async def test_pick_radio_flow(hass: HomeAssistant, radio_type) -> None:
    """Test radio picker."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: "manual_pick_radio_type"},
        data={CONF_RADIO_TYPE: radio_type},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "manual_port_config"


async def test_user_flow_existing_config_entry(hass: HomeAssistant) -> None:
    """Test if config entry already exists."""
    MockConfigEntry(
        domain=DOMAIN, data={CONF_DEVICE: {CONF_DEVICE_PATH: "/dev/ttyUSB1"}}
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    assert result["type"] == "abort"


@patch(f"bellows.{PROBE_FUNCTION_PATH}", return_value=False)
@patch(f"zigpy_deconz.{PROBE_FUNCTION_PATH}", return_value=False)
@patch(f"zigpy_zigate.{PROBE_FUNCTION_PATH}", return_value=False)
@patch(f"zigpy_znp.{PROBE_FUNCTION_PATH}", return_value=True)
async def test_detect_radio_type_success(
    znp_probe, zigate_probe, deconz_probe, bellows_probe, hass: HomeAssistant
) -> None:
    """Test detect radios successfully."""

    handler = config_flow.ZhaConfigFlowHandler()
    handler._radio_mgr.device_path = "/dev/null"

    await handler._radio_mgr.detect_radio_type()

    assert handler._radio_mgr.radio_type == RadioType.znp
    assert (
        handler._radio_mgr.device_settings[zigpy.config.CONF_DEVICE_PATH] == "/dev/null"
    )

    assert bellows_probe.await_count == 1
    assert znp_probe.await_count == 1
    assert deconz_probe.await_count == 0
    assert zigate_probe.await_count == 0


@patch(
    f"bellows.{PROBE_FUNCTION_PATH}",
    return_value={"new_setting": 123, zigpy.config.CONF_DEVICE_PATH: "/dev/null"},
)
@patch(f"zigpy_deconz.{PROBE_FUNCTION_PATH}", return_value=False)
@patch(f"zigpy_zigate.{PROBE_FUNCTION_PATH}", return_value=False)
@patch(f"zigpy_znp.{PROBE_FUNCTION_PATH}", return_value=False)
async def test_detect_radio_type_success_with_settings(
    znp_probe, zigate_probe, deconz_probe, bellows_probe, hass: HomeAssistant
) -> None:
    """Test detect radios successfully but probing returns new settings."""

    handler = config_flow.ZhaConfigFlowHandler()
    handler._radio_mgr.device_path = "/dev/null"
    await handler._radio_mgr.detect_radio_type()

    assert handler._radio_mgr.radio_type == RadioType.ezsp
    assert handler._radio_mgr.device_settings["new_setting"] == 123
    assert (
        handler._radio_mgr.device_settings[zigpy.config.CONF_DEVICE_PATH] == "/dev/null"
    )

    assert bellows_probe.await_count == 1
    assert znp_probe.await_count == 0
    assert deconz_probe.await_count == 0
    assert zigate_probe.await_count == 0


@patch(f"bellows.{PROBE_FUNCTION_PATH}", return_value=False)
async def test_user_port_config_fail(probe_mock, hass: HomeAssistant) -> None:
    """Test port config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: "manual_pick_radio_type"},
        data={CONF_RADIO_TYPE: RadioType.ezsp.description},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={zigpy.config.CONF_DEVICE_PATH: "/dev/ttyUSB33"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "manual_port_config"
    assert result["errors"]["base"] == "cannot_connect"
    assert probe_mock.await_count == 1


@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
@patch(f"bellows.{PROBE_FUNCTION_PATH}", return_value=True)
async def test_user_port_config(probe_mock, hass: HomeAssistant) -> None:
    """Test port config."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: "manual_pick_radio_type"},
        data={CONF_RADIO_TYPE: RadioType.ezsp.description},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={zigpy.config.CONF_DEVICE_PATH: "/dev/ttyUSB33"},
    )

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "choose_formation_strategy"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"next_step_id": config_flow.FORMATION_REUSE_SETTINGS},
    )
    await hass.async_block_till_done()

    assert (
        result2["data"][zigpy.config.CONF_DEVICE][zigpy.config.CONF_DEVICE_PATH]
        == "/dev/ttyUSB33"
    )
    assert result2["data"][CONF_RADIO_TYPE] == "ezsp"
    assert probe_mock.await_count == 1


@pytest.mark.parametrize(
    ("old_type", "new_type"),
    [
        ("ezsp", "ezsp"),
        ("ti_cc", "znp"),  # only one that should change
        ("znp", "znp"),
        ("deconz", "deconz"),
    ],
)
async def test_migration_ti_cc_to_znp(
    old_type, new_type, hass: HomeAssistant, config_entry
) -> None:
    """Test zigpy-cc to zigpy-znp config migration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=old_type + new_type,
        data={
            CONF_RADIO_TYPE: old_type,
            CONF_DEVICE: {
                CONF_DEVICE_PATH: "/dev/ttyUSB1",
                CONF_BAUDRATE: 115200,
                CONF_FLOWCONTROL: None,
            },
        },
    )

    config_entry.version = 2
    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.zha.async_setup_entry", return_value=True):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.version > 2
    assert config_entry.data[CONF_RADIO_TYPE] == new_type


@pytest.mark.parametrize("onboarded", [True, False])
@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
async def test_hardware(onboarded, hass: HomeAssistant) -> None:
    """Test hardware flow."""
    data = {
        "name": "Yellow",
        "radio_type": "efr32",
        "port": {
            "path": "/dev/ttyAMA1",
            "baudrate": 115200,
            "flow_control": "hardware",
        },
    }
    with patch(
        "homeassistant.components.onboarding.async_is_onboarded", return_value=onboarded
    ):
        result1 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "hardware"}, data=data
        )

    if onboarded:
        # Confirm discovery
        assert result1["type"] == FlowResultType.FORM
        assert result1["step_id"] == "confirm"

        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            user_input={},
        )
    else:
        # No need to confirm
        result2 = result1

    assert result2["type"] == FlowResultType.MENU
    assert result2["step_id"] == "choose_formation_strategy"

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={"next_step_id": config_flow.FORMATION_REUSE_SETTINGS},
    )
    await hass.async_block_till_done()

    assert result3["title"] == "Yellow"
    assert result3["data"] == {
        CONF_DEVICE: {
            CONF_BAUDRATE: 115200,
            CONF_FLOWCONTROL: "hardware",
            CONF_DEVICE_PATH: "/dev/ttyAMA1",
        },
        CONF_RADIO_TYPE: "ezsp",
    }


async def test_hardware_already_setup(hass: HomeAssistant) -> None:
    """Test hardware flow -- already setup."""

    MockConfigEntry(
        domain=DOMAIN, data={CONF_DEVICE: {CONF_DEVICE_PATH: "/dev/ttyUSB1"}}
    ).add_to_hass(hass)

    data = {
        "name": "Yellow",
        "radio_type": "efr32",
        "port": {
            "path": "/dev/ttyAMA1",
            "baudrate": 115200,
            "flow_control": "hardware",
        },
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "hardware"}, data=data
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.parametrize(
    "data", (None, {}, {"radio_type": "best_radio"}, {"radio_type": "efr32"})
)
async def test_hardware_invalid_data(hass: HomeAssistant, data) -> None:
    """Test onboarding flow -- invalid data."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "hardware"}, data=data
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "invalid_hardware_data"


def test_allow_overwrite_ezsp_ieee() -> None:
    """Test modifying the backup to allow bellows to override the IEEE address."""
    backup = zigpy.backups.NetworkBackup()
    new_backup = radio_manager._allow_overwrite_ezsp_ieee(backup)

    assert backup != new_backup
    assert new_backup.network_info.stack_specific["ezsp"][EZSP_OVERWRITE_EUI64] is True


def test_prevent_overwrite_ezsp_ieee() -> None:
    """Test modifying the backup to prevent bellows from overriding the IEEE address."""
    backup = zigpy.backups.NetworkBackup()
    backup.network_info.stack_specific["ezsp"] = {EZSP_OVERWRITE_EUI64: True}
    new_backup = radio_manager._prevent_overwrite_ezsp_ieee(backup)

    assert backup != new_backup
    assert not new_backup.network_info.stack_specific.get("ezsp", {}).get(
        EZSP_OVERWRITE_EUI64
    )


@pytest.fixture
def pick_radio(hass):
    """Fixture for the first step of the config flow (where a radio is picked)."""

    async def wrapper(radio_type):
        port = com_port()
        port_select = f"{port}, s/n: {port.serial_number} - {port.manufacturer}"

        with patch(
            "homeassistant.components.zha.radio_manager.ZhaRadioManager.detect_radio_type",
            mock_detect_radio_type(radio_type=radio_type),
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={CONF_SOURCE: SOURCE_USER},
                data={
                    zigpy.config.CONF_DEVICE_PATH: port_select,
                },
            )

        assert result["type"] == FlowResultType.MENU
        assert result["step_id"] == "choose_formation_strategy"

        return result, port

    p1 = patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
    p2 = patch("homeassistant.components.zha.async_setup_entry")

    with p1, p2:
        yield wrapper


async def test_strategy_no_network_settings(
    pick_radio, mock_app, hass: HomeAssistant
) -> None:
    """Test formation strategy when no network settings are present."""
    mock_app.load_network_info = MagicMock(side_effect=NetworkNotFormed())

    result, port = await pick_radio(RadioType.ezsp)
    assert (
        config_flow.FORMATION_REUSE_SETTINGS
        not in result["data_schema"].schema["next_step_id"].container
    )


async def test_formation_strategy_form_new_network(
    pick_radio, mock_app, hass: HomeAssistant
) -> None:
    """Test forming a new network."""
    result, port = await pick_radio(RadioType.ezsp)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"next_step_id": config_flow.FORMATION_FORM_NEW_NETWORK},
    )
    await hass.async_block_till_done()

    # A new network will be formed
    mock_app.form_network.assert_called_once()

    assert result2["type"] == FlowResultType.CREATE_ENTRY


async def test_formation_strategy_form_initial_network(
    pick_radio, mock_app, hass: HomeAssistant
) -> None:
    """Test forming a new network, with no previous settings on the radio."""
    mock_app.load_network_info = AsyncMock(side_effect=NetworkNotFormed())

    result, port = await pick_radio(RadioType.ezsp)
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"next_step_id": config_flow.FORMATION_FORM_INITIAL_NETWORK},
    )
    await hass.async_block_till_done()

    # A new network will be formed
    mock_app.form_network.assert_called_once()

    assert result2["type"] == FlowResultType.CREATE_ENTRY


@patch(f"zigpy_znp.{PROBE_FUNCTION_PATH}", AsyncMock(return_value=True))
async def test_onboarding_auto_formation_new_hardware(
    mock_app, hass: HomeAssistant
) -> None:
    """Test auto network formation with new hardware during onboarding."""
    mock_app.load_network_info = AsyncMock(side_effect=NetworkNotFormed())
    discovery_info = usb.UsbServiceInfo(
        device="/dev/ttyZIGBEE",
        pid="AAAA",
        vid="AAAA",
        serial_number="1234",
        description="zigbee radio",
        manufacturer="test",
    )

    with patch(
        "homeassistant.components.onboarding.async_is_onboarded", return_value=False
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USB}, data=discovery_info
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "zigbee radio"
    assert result["data"] == {
        "device": {
            "baudrate": 115200,
            "flow_control": None,
            "path": "/dev/ttyZIGBEE",
        },
        CONF_RADIO_TYPE: "znp",
    }


async def test_formation_strategy_reuse_settings(
    pick_radio, mock_app, hass: HomeAssistant
) -> None:
    """Test reusing existing network settings."""
    result, port = await pick_radio(RadioType.ezsp)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"next_step_id": config_flow.FORMATION_REUSE_SETTINGS},
    )
    await hass.async_block_till_done()

    # Nothing will be written when settings are reused
    mock_app.write_network_info.assert_not_called()

    assert result2["type"] == FlowResultType.CREATE_ENTRY


@patch("homeassistant.components.zha.config_flow.process_uploaded_file")
def test_parse_uploaded_backup(process_mock) -> None:
    """Test parsing uploaded backup files."""
    backup = zigpy.backups.NetworkBackup()

    text = json.dumps(backup.as_dict())
    process_mock.return_value.__enter__.return_value.read_text.return_value = text

    handler = config_flow.ZhaConfigFlowHandler()
    parsed_backup = handler._parse_uploaded_backup(str(uuid.uuid4()))

    assert backup == parsed_backup


@patch("homeassistant.components.zha.radio_manager._allow_overwrite_ezsp_ieee")
async def test_formation_strategy_restore_manual_backup_non_ezsp(
    allow_overwrite_ieee_mock, pick_radio, mock_app, hass: HomeAssistant
) -> None:
    """Test restoring a manual backup on non-EZSP coordinators."""
    result, port = await pick_radio(RadioType.znp)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"next_step_id": config_flow.FORMATION_UPLOAD_MANUAL_BACKUP},
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "upload_manual_backup"

    with patch(
        "homeassistant.components.zha.config_flow.ZhaConfigFlowHandler._parse_uploaded_backup",
        return_value=zigpy.backups.NetworkBackup(),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            user_input={config_flow.UPLOADED_BACKUP_FILE: str(uuid.uuid4())},
        )

    mock_app.backups.restore_backup.assert_called_once()
    allow_overwrite_ieee_mock.assert_not_called()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"][CONF_RADIO_TYPE] == "znp"


@patch("homeassistant.components.zha.radio_manager._allow_overwrite_ezsp_ieee")
async def test_formation_strategy_restore_manual_backup_overwrite_ieee_ezsp(
    allow_overwrite_ieee_mock, pick_radio, mock_app, backup, hass: HomeAssistant
) -> None:
    """Test restoring a manual backup on EZSP coordinators (overwrite IEEE)."""
    result, port = await pick_radio(RadioType.ezsp)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"next_step_id": config_flow.FORMATION_UPLOAD_MANUAL_BACKUP},
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "upload_manual_backup"

    with patch(
        "homeassistant.components.zha.config_flow.ZhaConfigFlowHandler._parse_uploaded_backup",
        return_value=backup,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            user_input={config_flow.UPLOADED_BACKUP_FILE: str(uuid.uuid4())},
        )

    assert result3["type"] == FlowResultType.FORM
    assert result3["step_id"] == "maybe_confirm_ezsp_restore"

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        user_input={config_flow.OVERWRITE_COORDINATOR_IEEE: True},
    )

    allow_overwrite_ieee_mock.assert_called_once()
    mock_app.backups.restore_backup.assert_called_once()

    assert result4["type"] == FlowResultType.CREATE_ENTRY
    assert result4["data"][CONF_RADIO_TYPE] == "ezsp"


@patch("homeassistant.components.zha.radio_manager._allow_overwrite_ezsp_ieee")
async def test_formation_strategy_restore_manual_backup_ezsp(
    allow_overwrite_ieee_mock, pick_radio, mock_app, hass: HomeAssistant
) -> None:
    """Test restoring a manual backup on EZSP coordinators (don't overwrite IEEE)."""
    result, port = await pick_radio(RadioType.ezsp)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"next_step_id": config_flow.FORMATION_UPLOAD_MANUAL_BACKUP},
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "upload_manual_backup"

    backup = zigpy.backups.NetworkBackup()

    with patch(
        "homeassistant.components.zha.config_flow.ZhaConfigFlowHandler._parse_uploaded_backup",
        return_value=backup,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            user_input={config_flow.UPLOADED_BACKUP_FILE: str(uuid.uuid4())},
        )

    assert result3["type"] == FlowResultType.FORM
    assert result3["step_id"] == "maybe_confirm_ezsp_restore"

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        user_input={config_flow.OVERWRITE_COORDINATOR_IEEE: False},
    )

    allow_overwrite_ieee_mock.assert_not_called()
    mock_app.backups.restore_backup.assert_called_once_with(backup)

    assert result4["type"] == FlowResultType.CREATE_ENTRY
    assert result4["data"][CONF_RADIO_TYPE] == "ezsp"


async def test_formation_strategy_restore_manual_backup_invalid_upload(
    pick_radio, mock_app, hass: HomeAssistant
) -> None:
    """Test restoring a manual backup but an invalid file is uploaded."""
    result, port = await pick_radio(RadioType.ezsp)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"next_step_id": config_flow.FORMATION_UPLOAD_MANUAL_BACKUP},
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "upload_manual_backup"

    with patch(
        "homeassistant.components.zha.config_flow.ZhaConfigFlowHandler._parse_uploaded_backup",
        side_effect=ValueError("Invalid backup JSON"),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            user_input={config_flow.UPLOADED_BACKUP_FILE: str(uuid.uuid4())},
        )

    mock_app.backups.restore_backup.assert_not_called()

    assert result3["type"] == FlowResultType.FORM
    assert result3["step_id"] == "upload_manual_backup"
    assert result3["errors"]["base"] == "invalid_backup_json"


def test_format_backup_choice() -> None:
    """Test formatting zigpy NetworkBackup objects."""
    backup = zigpy.backups.NetworkBackup()
    backup.network_info.pan_id = zigpy.types.PanId(0x1234)
    backup.network_info.extended_pan_id = zigpy.types.EUI64.convert(
        "aa:bb:cc:dd:ee:ff:00:11"
    )

    with_ids = config_flow._format_backup_choice(backup, pan_ids=True)
    without_ids = config_flow._format_backup_choice(backup, pan_ids=False)

    assert with_ids.startswith(without_ids)
    assert "1234:aabbccddeeff0011" in with_ids
    assert "1234:aabbccddeeff0011" not in without_ids


@patch(
    "homeassistant.components.zha.config_flow._format_backup_choice",
    lambda s, **kwargs: "choice:" + repr(s),
)
@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
async def test_formation_strategy_restore_automatic_backup_ezsp(
    pick_radio, mock_app, make_backup, hass: HomeAssistant
) -> None:
    """Test restoring an automatic backup (EZSP radio)."""
    mock_app.backups.backups = [
        make_backup(),
        make_backup(),
        make_backup(),
    ]
    backup = mock_app.backups.backups[1]  # pick the second one
    backup.is_compatible_with = MagicMock(return_value=False)

    result, port = await pick_radio(RadioType.ezsp)
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"next_step_id": (config_flow.FORMATION_CHOOSE_AUTOMATIC_BACKUP)},
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "choose_automatic_backup"

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={
            config_flow.CHOOSE_AUTOMATIC_BACKUP: "choice:" + repr(backup),
        },
    )

    assert result3["type"] == FlowResultType.FORM
    assert result3["step_id"] == "maybe_confirm_ezsp_restore"

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        user_input={config_flow.OVERWRITE_COORDINATOR_IEEE: True},
    )

    mock_app.backups.restore_backup.assert_called_once()

    assert result4["type"] == FlowResultType.CREATE_ENTRY
    assert result4["data"][CONF_RADIO_TYPE] == "ezsp"


@patch(
    "homeassistant.components.zha.config_flow._format_backup_choice",
    lambda s, **kwargs: "choice:" + repr(s),
)
@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
@pytest.mark.parametrize("is_advanced", [True, False])
async def test_formation_strategy_restore_automatic_backup_non_ezsp(
    is_advanced, pick_radio, mock_app, make_backup, hass: HomeAssistant
) -> None:
    """Test restoring an automatic backup (non-EZSP radio)."""
    mock_app.backups.backups = [
        make_backup(backup_time_offset=5),
        make_backup(backup_time_offset=-3),
        make_backup(backup_time_offset=2),
    ]
    backup = mock_app.backups.backups[1]  # pick the second one
    backup.is_compatible_with = MagicMock(return_value=False)

    result, port = await pick_radio(RadioType.znp)

    with patch(
        "homeassistant.config_entries.ConfigFlow.show_advanced_options",
        new_callable=PropertyMock(return_value=is_advanced),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "next_step_id": (config_flow.FORMATION_CHOOSE_AUTOMATIC_BACKUP)
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "choose_automatic_backup"

    # We don't prompt for overwriting the IEEE address, since only EZSP needs this
    assert config_flow.OVERWRITE_COORDINATOR_IEEE not in result2["data_schema"].schema

    # The backup choices are ordered by date
    assert result2["data_schema"].schema["choose_automatic_backup"].container == [
        f"choice:{mock_app.backups.backups[0]!r}",
        f"choice:{mock_app.backups.backups[2]!r}",
        f"choice:{mock_app.backups.backups[1]!r}",
    ]

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={
            config_flow.CHOOSE_AUTOMATIC_BACKUP: f"choice:{backup!r}",
        },
    )

    mock_app.backups.restore_backup.assert_called_once_with(backup)

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"][CONF_RADIO_TYPE] == "znp"


@patch("homeassistant.components.zha.radio_manager._allow_overwrite_ezsp_ieee")
async def test_ezsp_restore_without_settings_change_ieee(
    allow_overwrite_ieee_mock, pick_radio, mock_app, backup, hass: HomeAssistant
) -> None:
    """Test a manual backup on EZSP coordinators without settings (no IEEE write)."""
    # Fail to load settings
    with patch.object(
        mock_app, "load_network_info", MagicMock(side_effect=NetworkNotFormed())
    ):
        result, port = await pick_radio(RadioType.ezsp)

    # Set the network state, it'll be picked up later after the load "succeeds"
    mock_app.state.node_info = backup.node_info
    mock_app.state.network_info = copy.deepcopy(backup.network_info)
    mock_app.state.network_info.network_key.tx_counter += 10000

    # Include the overwrite option, just in case someone uploads a backup with it
    backup.network_info.metadata["ezsp"] = {EZSP_OVERWRITE_EUI64: True}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"next_step_id": config_flow.FORMATION_UPLOAD_MANUAL_BACKUP},
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "upload_manual_backup"

    with patch(
        "homeassistant.components.zha.config_flow.ZhaConfigFlowHandler._parse_uploaded_backup",
        return_value=backup,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            user_input={config_flow.UPLOADED_BACKUP_FILE: str(uuid.uuid4())},
        )

    # We wrote settings when connecting
    allow_overwrite_ieee_mock.assert_not_called()
    mock_app.backups.restore_backup.assert_called_once_with(backup, create_new=False)

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"][CONF_RADIO_TYPE] == "ezsp"


@pytest.mark.parametrize(
    "async_unload_effect", [True, config_entries.OperationNotAllowed()]
)
@patch(
    "serial.tools.list_ports.comports",
    MagicMock(
        return_value=[
            com_port("/dev/SomePort"),
            com_port("/dev/ttyUSB0"),
            com_port("/dev/SomeOtherPort"),
        ]
    ),
)
@patch("homeassistant.components.zha.async_setup_entry", return_value=True)
async def test_options_flow_defaults(
    async_setup_entry, async_unload_effect, hass: HomeAssistant
) -> None:
    """Test options flow defaults match radio defaults."""

    entry = MockConfigEntry(
        version=config_flow.ZhaConfigFlowHandler.VERSION,
        domain=DOMAIN,
        data={
            CONF_DEVICE: {
                CONF_DEVICE_PATH: "/dev/ttyUSB0",
                CONF_BAUDRATE: 12345,
                CONF_FLOWCONTROL: None,
            },
            CONF_RADIO_TYPE: "znp",
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    flow = await hass.config_entries.options.async_init(entry.entry_id)

    async_setup_entry.reset_mock()

    # ZHA gets unloaded
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload",
        side_effect=[async_unload_effect],
    ) as mock_async_unload:
        result1 = await hass.config_entries.options.async_configure(
            flow["flow_id"], user_input={}
        )

    mock_async_unload.assert_called_once_with(entry.entry_id)

    # Unload it ourselves
    entry.state = config_entries.ConfigEntryState.NOT_LOADED

    # Reconfigure ZHA
    assert result1["step_id"] == "prompt_migrate_or_reconfigure"
    result2 = await hass.config_entries.options.async_configure(
        flow["flow_id"],
        user_input={"next_step_id": config_flow.OPTIONS_INTENT_RECONFIGURE},
    )

    # Current path is the default
    assert result2["step_id"] == "choose_serial_port"
    assert "/dev/ttyUSB0" in result2["data_schema"]({})[CONF_DEVICE_PATH]

    # Autoprobing fails, we have to manually choose the radio type
    result3 = await hass.config_entries.options.async_configure(
        flow["flow_id"], user_input={}
    )

    # Current radio type is the default
    assert result3["step_id"] == "manual_pick_radio_type"
    assert result3["data_schema"]({})[CONF_RADIO_TYPE] == RadioType.znp.description

    # Continue on to port settings
    result4 = await hass.config_entries.options.async_configure(
        flow["flow_id"],
        user_input={
            CONF_RADIO_TYPE: RadioType.znp.description,
        },
    )

    # The defaults match our current settings
    assert result4["step_id"] == "manual_port_config"
    assert result4["data_schema"]({}) == entry.data[CONF_DEVICE]

    with patch(f"zigpy_znp.{PROBE_FUNCTION_PATH}", AsyncMock(return_value=True)):
        # Change the serial port path
        result5 = await hass.config_entries.options.async_configure(
            flow["flow_id"],
            user_input={
                # Change everything
                CONF_DEVICE_PATH: "/dev/new_serial_port",
                CONF_BAUDRATE: 54321,
                CONF_FLOWCONTROL: "software",
            },
        )

    # The radio has been detected, we can move on to creating the config entry
    assert result5["step_id"] == "choose_formation_strategy"

    async_setup_entry.assert_not_called()

    result6 = await hass.config_entries.options.async_configure(
        result1["flow_id"],
        user_input={"next_step_id": config_flow.FORMATION_REUSE_SETTINGS},
    )
    await hass.async_block_till_done()

    assert result6["type"] == FlowResultType.CREATE_ENTRY
    assert result6["data"] == {}

    # The updated entry contains correct settings
    assert entry.data == {
        CONF_DEVICE: {
            CONF_DEVICE_PATH: "/dev/new_serial_port",
            CONF_BAUDRATE: 54321,
            CONF_FLOWCONTROL: "software",
        },
        CONF_RADIO_TYPE: "znp",
    }

    # ZHA was started again
    assert async_setup_entry.call_count == 1


@patch(
    "serial.tools.list_ports.comports",
    MagicMock(
        return_value=[
            com_port("/dev/SomePort"),
            com_port("/dev/SomeOtherPort"),
        ]
    ),
)
@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
async def test_options_flow_defaults_socket(hass: HomeAssistant) -> None:
    """Test options flow defaults work even for serial ports that can't be listed."""

    entry = MockConfigEntry(
        version=config_flow.ZhaConfigFlowHandler.VERSION,
        domain=DOMAIN,
        data={
            CONF_DEVICE: {
                CONF_DEVICE_PATH: "socket://localhost:5678",
                CONF_BAUDRATE: 12345,
                CONF_FLOWCONTROL: None,
            },
            CONF_RADIO_TYPE: "znp",
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    flow = await hass.config_entries.options.async_init(entry.entry_id)

    # ZHA gets unloaded
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload", return_value=True
    ):
        result1 = await hass.config_entries.options.async_configure(
            flow["flow_id"], user_input={}
        )

    assert result1["step_id"] == "prompt_migrate_or_reconfigure"
    result2 = await hass.config_entries.options.async_configure(
        flow["flow_id"],
        user_input={"next_step_id": config_flow.OPTIONS_INTENT_RECONFIGURE},
    )

    # Radio path must be manually entered
    assert result2["step_id"] == "choose_serial_port"
    assert result2["data_schema"]({})[CONF_DEVICE_PATH] == config_flow.CONF_MANUAL_PATH

    result3 = await hass.config_entries.options.async_configure(
        flow["flow_id"], user_input={}
    )

    # Current radio type is the default
    assert result3["step_id"] == "manual_pick_radio_type"
    assert result3["data_schema"]({})[CONF_RADIO_TYPE] == RadioType.znp.description

    # Continue on to port settings
    result4 = await hass.config_entries.options.async_configure(
        flow["flow_id"], user_input={}
    )

    # The defaults match our current settings
    assert result4["step_id"] == "manual_port_config"
    assert result4["data_schema"]({}) == entry.data[CONF_DEVICE]

    with patch(f"zigpy_znp.{PROBE_FUNCTION_PATH}", AsyncMock(return_value=True)):
        result5 = await hass.config_entries.options.async_configure(
            flow["flow_id"], user_input={}
        )

    assert result5["step_id"] == "choose_formation_strategy"


@patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
@patch("homeassistant.components.zha.async_setup_entry", return_value=True)
async def test_options_flow_restarts_running_zha_if_cancelled(
    async_setup_entry, hass: HomeAssistant
) -> None:
    """Test options flow restarts a previously-running ZHA if it's cancelled."""

    entry = MockConfigEntry(
        version=config_flow.ZhaConfigFlowHandler.VERSION,
        domain=DOMAIN,
        data={
            CONF_DEVICE: {
                CONF_DEVICE_PATH: "socket://localhost:5678",
                CONF_BAUDRATE: 12345,
                CONF_FLOWCONTROL: None,
            },
            CONF_RADIO_TYPE: "znp",
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    flow = await hass.config_entries.options.async_init(entry.entry_id)

    # ZHA gets unloaded
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload", return_value=True
    ):
        result1 = await hass.config_entries.options.async_configure(
            flow["flow_id"], user_input={}
        )

    entry.state = config_entries.ConfigEntryState.NOT_LOADED

    assert result1["step_id"] == "prompt_migrate_or_reconfigure"
    result2 = await hass.config_entries.options.async_configure(
        flow["flow_id"],
        user_input={"next_step_id": config_flow.OPTIONS_INTENT_RECONFIGURE},
    )

    # Radio path must be manually entered
    assert result2["step_id"] == "choose_serial_port"

    async_setup_entry.reset_mock()

    # Abort the flow
    hass.config_entries.options.async_abort(result2["flow_id"])
    await hass.async_block_till_done()

    # ZHA was set up once more
    async_setup_entry.assert_called_once_with(hass, entry)


@patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
async def test_options_flow_migration_reset_old_adapter(
    hass: HomeAssistant, mock_app
) -> None:
    """Test options flow for migrating from an old radio."""

    entry = MockConfigEntry(
        version=config_flow.ZhaConfigFlowHandler.VERSION,
        domain=DOMAIN,
        data={
            CONF_DEVICE: {
                CONF_DEVICE_PATH: "/dev/serial/by-id/old_radio",
                CONF_BAUDRATE: 12345,
                CONF_FLOWCONTROL: None,
            },
            CONF_RADIO_TYPE: "znp",
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    flow = await hass.config_entries.options.async_init(entry.entry_id)

    # ZHA gets unloaded
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload", return_value=True
    ):
        result1 = await hass.config_entries.options.async_configure(
            flow["flow_id"], user_input={}
        )

    entry.state = config_entries.ConfigEntryState.NOT_LOADED

    assert result1["step_id"] == "prompt_migrate_or_reconfigure"
    result2 = await hass.config_entries.options.async_configure(
        flow["flow_id"],
        user_input={"next_step_id": config_flow.OPTIONS_INTENT_MIGRATE},
    )

    # User must explicitly approve radio reset
    assert result2["step_id"] == "intent_migrate"

    mock_app.reset_network_info = AsyncMock()

    result3 = await hass.config_entries.options.async_configure(
        flow["flow_id"],
        user_input={},
    )

    mock_app.reset_network_info.assert_awaited_once()

    # Now we can unplug the old radio
    assert result3["step_id"] == "instruct_unplug"

    # And move on to choosing the new radio
    result4 = await hass.config_entries.options.async_configure(
        flow["flow_id"],
        user_input={},
    )
    assert result4["step_id"] == "choose_serial_port"


async def test_config_flow_port_yellow_port_name(hass: HomeAssistant) -> None:
    """Test config flow serial port name for Yellow Zigbee radio."""
    port = com_port(device="/dev/ttyAMA1")
    port.serial_number = None
    port.manufacturer = None
    port.description = None

    with patch(
        "homeassistant.components.zha.config_flow.yellow_hardware.async_info"
    ), patch("serial.tools.list_ports.comports", MagicMock(return_value=[port])):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
        )

    assert (
        result["data_schema"].schema["path"].container[0]
        == "/dev/ttyAMA1 - Yellow Zigbee module - Nabu Casa"
    )


async def test_config_flow_port_multiprotocol_port_name(hass: HomeAssistant) -> None:
    """Test config flow serial port name for multiprotocol add-on."""

    with patch(
        "homeassistant.components.hassio.addon_manager.AddonManager.async_get_addon_info"
    ) as async_get_addon_info, patch(
        "serial.tools.list_ports.comports", MagicMock(return_value=[])
    ):
        async_get_addon_info.return_value.state = AddonState.RUNNING
        async_get_addon_info.return_value.hostname = "core-silabs-multiprotocol"

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
        )

    assert (
        result["data_schema"].schema["path"].container[0]
        == "socket://core-silabs-multiprotocol:9999 - Multiprotocol add-on - Nabu Casa"
    )
