"""Tests for ZHA config flow."""

import json
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch
import uuid

import pytest
import serial.tools.list_ports
import zigpy.config
from zigpy.config import CONF_DEVICE, CONF_DEVICE_PATH
from zigpy.exceptions import NetworkNotFormed
import zigpy.types

from homeassistant import config_entries
from homeassistant.components import ssdp, usb, zeroconf
from homeassistant.components.ssdp import ATTR_UPNP_MANUFACTURER_URL, ATTR_UPNP_SERIAL
from homeassistant.components.zha import config_flow
from homeassistant.components.zha.core.const import (
    CONF_BAUDRATE,
    CONF_FLOWCONTROL,
    CONF_RADIO_TYPE,
    DOMAIN,
    RadioType,
)
from homeassistant.config_entries import (
    SOURCE_SSDP,
    SOURCE_USB,
    SOURCE_USER,
    SOURCE_ZEROCONF,
)
from homeassistant.const import CONF_SOURCE
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

PROBE_FUNCTION_PATH = "zigbee.application.ControllerApplication.probe"


@pytest.fixture(autouse=True)
def disable_platform_only():
    """Disable platforms to speed up tests."""
    with patch("homeassistant.components.zha.PLATFORMS", []):
        yield


@pytest.fixture(autouse=True)
def mock_app():
    """Mock zigpy app interface."""
    mock_app = AsyncMock()
    mock_app.backups.backups = []

    with patch(
        "zigpy.application.ControllerApplication.new", AsyncMock(return_value=mock_app)
    ):
        yield mock_app


def mock_detect_radio_type(radio_type=RadioType.ezsp, ret=True):
    """Mock `_detect_radio_type` that just sets the appropriate attributes."""

    async def detect(self):
        self._radio_type = radio_type
        self._device_settings = radio_type.controller.SCHEMA_DEVICE(
            {CONF_DEVICE_PATH: self._device_path}
        )

        return ret

    return detect


def com_port():
    """Mock of a serial port."""
    port = serial.tools.list_ports_common.ListPortInfo("/dev/ttyUSB1234")
    port.serial_number = "1234"
    port.manufacturer = "Virtual serial port"
    port.device = "/dev/ttyUSB1234"
    port.description = "Some serial port"

    return port


@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
@patch(f"zigpy_znp.{PROBE_FUNCTION_PATH}", AsyncMock(return_value=True))
async def test_discovery(hass):
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
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], user_input={}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "socket://192.168.1.200:6638"
    assert result["data"] == {
        CONF_DEVICE: {
            CONF_BAUDRATE: 115200,
            CONF_FLOWCONTROL: None,
            CONF_DEVICE_PATH: "socket://192.168.1.200:6638",
        },
        CONF_RADIO_TYPE: "znp",
    }


@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
@patch(f"zigpy_zigate.{PROBE_FUNCTION_PATH}")
async def test_zigate_via_zeroconf(setup_entry_mock, hass):
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
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], user_input={}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "socket://192.168.1.200:1234"
    assert result["data"] == {
        CONF_DEVICE: {
            CONF_DEVICE_PATH: "socket://192.168.1.200:1234",
        },
        CONF_RADIO_TYPE: "zigate",
    }


@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
@patch(f"bellows.{PROBE_FUNCTION_PATH}", AsyncMock(return_value=True))
async def test_efr32_via_zeroconf(hass):
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
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], user_input={"baudrate": 115200}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "socket://192.168.1.200:6638"
    assert result["data"] == {
        CONF_DEVICE: {
            CONF_DEVICE_PATH: "socket://192.168.1.200:6638",
            CONF_BAUDRATE: 115200,
            CONF_FLOWCONTROL: "software",
        },
        CONF_RADIO_TYPE: "ezsp",
    }


@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
@patch(f"bellows.{PROBE_FUNCTION_PATH}", AsyncMock(return_value=True))
async def test_discovery_via_zeroconf_ip_change(hass):
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
@patch(f"bellows.{PROBE_FUNCTION_PATH}", AsyncMock(return_value=True))
async def test_discovery_via_zeroconf_ip_change_ignored(hass):
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


@patch(f"bellows.{PROBE_FUNCTION_PATH}", AsyncMock(return_value=True))
async def test_discovery_via_usb(hass):
    """Test usb flow -- radio detected."""
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

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "choose_formation_strategy"

    with patch("homeassistant.components.zha.async_setup_entry"):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            user_input={
                config_flow.FORMATION_STRATEGY: config_flow.FORMATION_REUSE_SETTINGS
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "zigbee radio"
    assert result3["data"] == {
        "device": {
            "baudrate": 57600,
            "flow_control": "software",
            "path": "/dev/ttyZIGBEE",
        },
        CONF_RADIO_TYPE: "ezsp",
    }


@patch(f"zigpy_zigate.{PROBE_FUNCTION_PATH}", return_value=True)
async def test_zigate_discovery_via_usb(probe_mock, hass):
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
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "choose_formation_strategy"

    with patch("homeassistant.components.zha.async_setup_entry"):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            user_input={
                config_flow.FORMATION_STRATEGY: config_flow.FORMATION_REUSE_SETTINGS
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "zigate radio"
    assert result3["data"] == {
        "device": {
            "path": "/dev/ttyZIGBEE",
        },
        CONF_RADIO_TYPE: "zigate",
    }


@patch(f"bellows.{PROBE_FUNCTION_PATH}", return_value=False)
async def test_discovery_via_usb_no_radio(probe_mock, hass):
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

    with patch("homeassistant.components.zha.async_setup_entry"):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "usb_probe_failed"


@patch(f"bellows.{PROBE_FUNCTION_PATH}", AsyncMock(return_value=True))
async def test_discovery_via_usb_already_setup(hass):
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
async def test_discovery_via_usb_path_changes(hass):
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


@patch(f"bellows.{PROBE_FUNCTION_PATH}", AsyncMock(return_value=True))
async def test_discovery_via_usb_deconz_already_discovered(hass):
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


@patch(f"bellows.{PROBE_FUNCTION_PATH}", AsyncMock(return_value=True))
async def test_discovery_via_usb_deconz_already_setup(hass):
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


@patch(f"bellows.{PROBE_FUNCTION_PATH}", AsyncMock(return_value=True))
async def test_discovery_via_usb_deconz_ignored(hass):
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


@patch(f"bellows.{PROBE_FUNCTION_PATH}", AsyncMock(return_value=True))
async def test_discovery_via_usb_zha_ignored_updates(hass):
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
@patch(f"bellows.{PROBE_FUNCTION_PATH}", AsyncMock(return_value=True))
async def test_discovery_already_setup(hass):
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
    "homeassistant.components.zha.config_flow.ZhaFlowHandler._detect_radio_type",
    mock_detect_radio_type(radio_type=RadioType.deconz),
)
@patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
async def test_user_flow(hass):
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
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "choose_formation_strategy"

    with patch("homeassistant.components.zha.async_setup_entry"):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                config_flow.FORMATION_STRATEGY: config_flow.FORMATION_REUSE_SETTINGS
            },
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
    "homeassistant.components.zha.config_flow.ZhaFlowHandler._detect_radio_type",
    mock_detect_radio_type(ret=False),
)
@patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
async def test_user_flow_not_detected(hass):
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
async def test_user_flow_show_form(hass):
    """Test user step form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


@patch("serial.tools.list_ports.comports", MagicMock(return_value=[]))
async def test_user_flow_show_manual(hass):
    """Test user flow manual entry when no comport detected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "manual_pick_radio_type"


async def test_user_flow_manual(hass):
    """Test user flow manual entry."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={zigpy.config.CONF_DEVICE_PATH: config_flow.CONF_MANUAL_PATH},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "manual_pick_radio_type"


@pytest.mark.parametrize("radio_type", RadioType.list())
async def test_pick_radio_flow(hass, radio_type):
    """Test radio picker."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: "manual_pick_radio_type"},
        data={CONF_RADIO_TYPE: radio_type},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "manual_port_config"


async def test_user_flow_existing_config_entry(hass):
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
    znp_probe, zigate_probe, deconz_probe, bellows_probe, hass
):
    """Test detect radios successfully."""

    handler = config_flow.ZhaFlowHandler()
    handler._device_path = "/dev/null"

    await handler._detect_radio_type()

    assert handler._radio_type == RadioType.znp
    assert handler._device_settings[zigpy.config.CONF_DEVICE_PATH] == "/dev/null"

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
    znp_probe, zigate_probe, deconz_probe, bellows_probe, hass
):
    """Test detect radios successfully but probing returns new settings."""

    handler = config_flow.ZhaFlowHandler()
    handler._device_path = "/dev/null"
    await handler._detect_radio_type()

    assert handler._radio_type == RadioType.ezsp
    assert handler._device_settings["new_setting"] == 123
    assert handler._device_settings[zigpy.config.CONF_DEVICE_PATH] == "/dev/null"

    assert bellows_probe.await_count == 1
    assert znp_probe.await_count == 0
    assert deconz_probe.await_count == 0
    assert zigate_probe.await_count == 0


@patch(f"bellows.{PROBE_FUNCTION_PATH}", return_value=False)
async def test_user_port_config_fail(probe_mock, hass):
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
async def test_user_port_config(probe_mock, hass):
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

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"].startswith("/dev/ttyUSB33")
    assert (
        result["data"][zigpy.config.CONF_DEVICE][zigpy.config.CONF_DEVICE_PATH]
        == "/dev/ttyUSB33"
    )
    assert result["data"][CONF_RADIO_TYPE] == "ezsp"
    assert probe_mock.await_count == 1


@pytest.mark.parametrize(
    "old_type,new_type",
    [
        ("ezsp", "ezsp"),
        ("ti_cc", "znp"),  # only one that should change
        ("znp", "znp"),
        ("deconz", "deconz"),
    ],
)
async def test_migration_ti_cc_to_znp(old_type, new_type, hass, config_entry):
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


@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
async def test_hardware_not_onboarded(hass):
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
        "homeassistant.components.onboarding.async_is_onboarded", return_value=False
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "hardware"}, data=data
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Yellow"
    assert result["data"] == {
        CONF_DEVICE: {
            CONF_BAUDRATE: 115200,
            CONF_FLOWCONTROL: "hardware",
            CONF_DEVICE_PATH: "/dev/ttyAMA1",
        },
        CONF_RADIO_TYPE: "ezsp",
    }


@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
async def test_hardware_onboarded(hass):
    """Test hardware flow."""
    data = {
        "radio_type": "efr32",
        "port": {
            "path": "/dev/ttyAMA1",
            "baudrate": 115200,
            "flow_control": "hardware",
        },
    }
    with patch(
        "homeassistant.components.onboarding.async_is_onboarded", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "hardware"}, data=data
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm_hardware"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "/dev/ttyAMA1"
    assert result["data"] == {
        CONF_DEVICE: {
            CONF_BAUDRATE: 115200,
            CONF_FLOWCONTROL: "hardware",
            CONF_DEVICE_PATH: "/dev/ttyAMA1",
        },
        CONF_RADIO_TYPE: "ezsp",
    }


async def test_hardware_already_setup(hass):
    """Test hardware flow -- already setup."""

    MockConfigEntry(
        domain=DOMAIN, data={CONF_DEVICE: {CONF_DEVICE_PATH: "/dev/ttyUSB1"}}
    ).add_to_hass(hass)

    data = {
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
async def test_hardware_invalid_data(hass, data):
    """Test onboarding flow -- invalid data."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "hardware"}, data=data
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "invalid_hardware_data"


def test_allow_overwrite_ezsp_ieee():
    """Test modifying the backup to allow bellows to override the IEEE address."""
    handler = config_flow.ZhaFlowHandler()

    backup = zigpy.backups.NetworkBackup()
    new_backup = handler._allow_overwrite_ezsp_ieee(backup)

    assert backup != new_backup
    assert (
        new_backup.network_info.stack_specific["ezsp"][
            "i_understand_i_can_update_eui64_only_once_and_i_still_want_to_do_it"
        ]
        is True
    )


@pytest.fixture
def pick_radio(hass):
    """Fixture for the first step of the config flow (where a radio is picked)."""

    async def wrapper(radio_type):
        port = com_port()
        port_select = f"{port}, s/n: {port.serial_number} - {port.manufacturer}"

        with patch(
            "homeassistant.components.zha.config_flow.ZhaFlowHandler._detect_radio_type",
            mock_detect_radio_type(radio_type=radio_type),
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={CONF_SOURCE: SOURCE_USER},
                data={
                    zigpy.config.CONF_DEVICE_PATH: port_select,
                },
            )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "choose_formation_strategy"

        return result, port

    p1 = patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
    p2 = patch("homeassistant.components.zha.async_setup_entry")

    with p1, p2:
        yield wrapper


async def test_strategy_no_network_settings(pick_radio, mock_app, hass):
    """Test formation strategy when no network settings are present."""
    mock_app.load_network_info = MagicMock(side_effect=NetworkNotFormed())

    result, port = await pick_radio(RadioType.ezsp)
    assert (
        config_flow.FORMATION_REUSE_SETTINGS
        not in result["data_schema"].schema[config_flow.FORMATION_STRATEGY].container
    )


async def test_formation_strategy_form_new_network(pick_radio, mock_app, hass):
    """Test forming a new network."""
    result, port = await pick_radio(RadioType.ezsp)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            config_flow.FORMATION_STRATEGY: config_flow.FORMATION_FORM_NEW_NETWORK
        },
    )
    await hass.async_block_till_done()

    # A new network will be formed
    mock_app.form_network.assert_called_once()

    assert result2["type"] == FlowResultType.CREATE_ENTRY


async def test_formation_strategy_reuse_settings(pick_radio, mock_app, hass):
    """Test reusing existing network settings."""
    result, port = await pick_radio(RadioType.ezsp)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            config_flow.FORMATION_STRATEGY: config_flow.FORMATION_REUSE_SETTINGS
        },
    )
    await hass.async_block_till_done()

    # Nothing will be written when settings are reused
    mock_app.write_network_info.assert_not_called()

    assert result2["type"] == FlowResultType.CREATE_ENTRY


@patch(
    "homeassistant.components.zha.config_flow.ZhaFlowHandler._allow_overwrite_ezsp_ieee"
)
async def test_formation_strategy_restore_manual_backup_non_ezsp(
    allow_overwrite_ieee_mock, pick_radio, mock_app, hass
):
    """Test restoring a manual backup on non-EZSP coordinators."""
    result, port = await pick_radio(RadioType.znp)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            config_flow.FORMATION_STRATEGY: config_flow.FORMATION_RESTORE_MANUAL_BACKUP
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "upload_manual_backup"

    # There is no need for the checkbox, writes are not permanent for non-EZSP sticks
    assert config_flow.OVERWRITE_COORDINATOR_IEEE not in result2["data_schema"].schema

    with patch(
        "homeassistant.components.zha.config_flow.process_uploaded_file"
    ) as upload:
        backup_json = json.dumps(zigpy.backups.NetworkBackup().as_dict())
        upload.return_value.__enter__.return_value.read_text.return_value = backup_json

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            user_input={config_flow.UPLOADED_BACKUP_FILE: str(uuid.uuid4())},
        )

    mock_app.backups.restore_backup.assert_called_once()
    allow_overwrite_ieee_mock.assert_not_called()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"][CONF_RADIO_TYPE] == "znp"


@patch(
    "homeassistant.components.zha.config_flow.ZhaFlowHandler._allow_overwrite_ezsp_ieee"
)
async def test_formation_strategy_restore_manual_backup_ezsp(
    allow_overwrite_ieee_mock, pick_radio, mock_app, hass
):
    """Test restoring a manual backup on EZSP coordinators."""
    result, port = await pick_radio(RadioType.ezsp)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            config_flow.FORMATION_STRATEGY: config_flow.FORMATION_RESTORE_MANUAL_BACKUP
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "upload_manual_backup"

    # We must prompt for overwriting the IEEE address
    assert config_flow.OVERWRITE_COORDINATOR_IEEE in result2["data_schema"].schema

    with patch(
        "homeassistant.components.zha.config_flow.process_uploaded_file"
    ) as upload:
        backup_json = json.dumps(zigpy.backups.NetworkBackup().as_dict())
        upload.return_value.__enter__.return_value.read_text.return_value = backup_json

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            user_input={config_flow.UPLOADED_BACKUP_FILE: str(uuid.uuid4())},
        )

    mock_app.backups.restore_backup.assert_called_once()
    allow_overwrite_ieee_mock.assert_called_once()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"][CONF_RADIO_TYPE] == "ezsp"


async def test_formation_strategy_restore_manual_backup_invalid_upload(
    pick_radio, mock_app, hass
):
    """Test restoring a manual backup but an invalid file is uploaded."""
    result, port = await pick_radio(RadioType.ezsp)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            config_flow.FORMATION_STRATEGY: config_flow.FORMATION_RESTORE_MANUAL_BACKUP
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "upload_manual_backup"

    # We must prompt for overwriting the IEEE address
    assert config_flow.OVERWRITE_COORDINATOR_IEEE in result2["data_schema"].schema

    with patch(
        "homeassistant.components.zha.config_flow.process_uploaded_file"
    ) as upload:
        upload.return_value.__enter__.return_value.read_text.return_value = "{}"

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            user_input={config_flow.UPLOADED_BACKUP_FILE: str(uuid.uuid4())},
        )

    mock_app.backups.restore_backup.assert_not_called()

    assert result3["type"] == FlowResultType.FORM
    assert result3["step_id"] == "upload_manual_backup"
    assert result3["errors"]["base"] == "invalid_backup_json"


def test_format_backup_choice():
    """Test formatting zigpy NetworkBackup objects."""
    backup = zigpy.backups.NetworkBackup()
    backup.network_info.pan_id = zigpy.types.PanId(0x1234)
    backup.network_info.extended_pan_id = zigpy.types.EUI64.convert(
        "aa:bb:cc:dd:ee:ff:00:11"
    )

    handler = config_flow.ZhaFlowHandler()
    with_ids = handler._format_backup_choice(backup, pan_ids=True)
    without_ids = handler._format_backup_choice(backup, pan_ids=False)

    assert with_ids.startswith(without_ids)
    assert "1234:aabbccddeeff0011" in with_ids
    assert "1234:aabbccddeeff0011" not in without_ids


@patch(
    "homeassistant.components.zha.config_flow.ZhaFlowHandler._format_backup_choice",
    lambda self, s, **kwargs: "choice:" + repr(s),
)
@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
async def test_formation_strategy_restore_automatic_backup_ezsp(
    pick_radio, mock_app, hass
):
    """Test restoring an automatic backup (EZSP radio)."""
    mock_app.backups.backups = [
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]
    backup = mock_app.backups.backups[1]  # pick the second one
    backup.is_compatible_with = MagicMock(return_value=False)

    result, port = await pick_radio(RadioType.ezsp)
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            config_flow.FORMATION_STRATEGY: (
                config_flow.FORMATION_RESTORE_AUTOMATIC_BACKUP
            )
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "restore_automatic_backup"

    # We must prompt for overwriting the IEEE address
    assert config_flow.OVERWRITE_COORDINATOR_IEEE in result2["data_schema"].schema

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={
            config_flow.CHOOSE_AUTOMATIC_BACKUP: "choice:" + repr(backup),
            config_flow.OVERWRITE_COORDINATOR_IEEE: True,
        },
    )

    mock_app.backups.restore_backup.assert_called_once()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"][CONF_RADIO_TYPE] == "ezsp"


@patch(
    "homeassistant.components.zha.config_flow.ZhaFlowHandler._format_backup_choice",
    lambda self, s, **kwargs: "choice:" + repr(s),
)
@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
@pytest.mark.parametrize("is_advanced", [True, False])
async def test_formation_strategy_restore_automatic_backup_non_ezsp(
    is_advanced, pick_radio, mock_app, hass
):
    """Test restoring an automatic backup (non-EZSP radio)."""
    mock_app.backups.backups = [
        MagicMock(),
        MagicMock(),
        MagicMock(),
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
                config_flow.FORMATION_STRATEGY: (
                    config_flow.FORMATION_RESTORE_AUTOMATIC_BACKUP
                )
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "restore_automatic_backup"

    # We must prompt for overwriting the IEEE address
    assert config_flow.OVERWRITE_COORDINATOR_IEEE not in result2["data_schema"].schema

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={
            config_flow.CHOOSE_AUTOMATIC_BACKUP: "choice:" + repr(backup),
        },
    )

    mock_app.backups.restore_backup.assert_called_once_with(backup)

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"][CONF_RADIO_TYPE] == "znp"
