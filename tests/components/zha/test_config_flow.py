"""Tests for ZHA config flow."""

from unittest.mock import AsyncMock, MagicMock, patch, sentinel

import pytest
import serial.tools.list_ports
import zigpy.config
from zigpy.config import CONF_DEVICE, CONF_DEVICE_PATH

from homeassistant import config_entries
from homeassistant.components import usb, zeroconf
from homeassistant.components.ssdp import (
    ATTR_SSDP_LOCATION,
    ATTR_UPNP_MANUFACTURER_URL,
    ATTR_UPNP_SERIAL,
)
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
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.common import MockConfigEntry


def com_port():
    """Mock of a serial port."""
    port = serial.tools.list_ports_common.ListPortInfo("/dev/ttyUSB1234")
    port.serial_number = "1234"
    port.manufacturer = "Virtual serial port"
    port.device = "/dev/ttyUSB1234"
    port.description = "Some serial port"

    return port


@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
@patch("zigpy_znp.zigbee.application.ControllerApplication.probe", return_value=True)
async def test_discovery(detect_mock, hass):
    """Test zeroconf flow -- radio detected."""
    service_info = zeroconf.ZeroconfServiceInfo(
        host="192.168.1.200",
        hostname="_tube_zb_gw._tcp.local.",
        name="mock_name",
        port=6053,
        properties={"name": "tube_123456"},
        type="mock_type",
    )
    flow = await hass.config_entries.flow.async_init(
        "zha", context={"source": SOURCE_ZEROCONF}, data=service_info
    )
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], user_input={}
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
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
@patch("zigpy_znp.zigbee.application.ControllerApplication.probe", return_value=True)
async def test_discovery_via_zeroconf_ip_change(detect_mock, hass):
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
        hostname="tube_zb_gw_cc2652p2_poe.local.",
        name="mock_name",
        port=6053,
        properties={"address": "tube_zb_gw_cc2652p2_poe.local"},
        type="mock_type",
    )
    result = await hass.config_entries.flow.async_init(
        "zha", context={"source": SOURCE_ZEROCONF}, data=service_info
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_DEVICE] == {
        CONF_DEVICE_PATH: "socket://192.168.1.22:6638",
        CONF_BAUDRATE: 115200,
        CONF_FLOWCONTROL: None,
    }


@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
@patch("zigpy_znp.zigbee.application.ControllerApplication.probe", return_value=True)
async def test_discovery_via_zeroconf_ip_change_ignored(detect_mock, hass):
    """Test zeroconf flow that was ignored gets updated."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="tube_zb_gw_cc2652p2_poe",
        source=config_entries.SOURCE_IGNORE,
    )
    entry.add_to_hass(hass)

    service_info = zeroconf.ZeroconfServiceInfo(
        host="192.168.1.22",
        hostname="tube_zb_gw_cc2652p2_poe.local.",
        name="mock_name",
        port=6053,
        properties={"address": "tube_zb_gw_cc2652p2_poe.local"},
        type="mock_type",
    )
    result = await hass.config_entries.flow.async_init(
        "zha", context={"source": SOURCE_ZEROCONF}, data=service_info
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_DEVICE] == {
        CONF_DEVICE_PATH: "socket://192.168.1.22:6638",
    }


@patch("zigpy_znp.zigbee.application.ControllerApplication.probe", return_value=True)
async def test_discovery_via_usb(detect_mock, hass):
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
        "zha", context={"source": SOURCE_USB}, data=discovery_info
    )
    await hass.async_block_till_done()
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "confirm"

    with patch("homeassistant.components.zha.async_setup_entry"):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert "zigbee radio" in result2["title"]
    assert result2["data"] == {
        "device": {
            "baudrate": 115200,
            "flow_control": None,
            "path": "/dev/ttyZIGBEE",
        },
        CONF_RADIO_TYPE: "znp",
    }


@patch("zigpy_znp.zigbee.application.ControllerApplication.probe", return_value=False)
async def test_discovery_via_usb_no_radio(detect_mock, hass):
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
        "zha", context={"source": SOURCE_USB}, data=discovery_info
    )
    await hass.async_block_till_done()
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "confirm"

    with patch("homeassistant.components.zha.async_setup_entry"):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_ABORT
    assert result2["reason"] == "usb_probe_failed"


@patch("zigpy_znp.zigbee.application.ControllerApplication.probe", return_value=True)
async def test_discovery_via_usb_already_setup(detect_mock, hass):
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
        "zha", context={"source": SOURCE_USB}, data=discovery_info
    )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_ABORT
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
        "zha", context={"source": SOURCE_USB}, data=discovery_info
    )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_DEVICE] == {
        CONF_DEVICE_PATH: "/dev/ttyZIGBEE",
        CONF_BAUDRATE: 115200,
        CONF_FLOWCONTROL: None,
    }


@patch("zigpy_znp.zigbee.application.ControllerApplication.probe", return_value=True)
async def test_discovery_via_usb_deconz_already_discovered(detect_mock, hass):
    """Test usb flow -- deconz discovered."""
    result = await hass.config_entries.flow.async_init(
        "deconz",
        data={
            ATTR_SSDP_LOCATION: "http://1.2.3.4:80/",
            ATTR_UPNP_MANUFACTURER_URL: "http://www.dresden-elektronik.de",
            ATTR_UPNP_SERIAL: "0000000000000000",
        },
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
        "zha", context={"source": SOURCE_USB}, data=discovery_info
    )
    await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "not_zha_device"


@patch("zigpy_znp.zigbee.application.ControllerApplication.probe", return_value=True)
async def test_discovery_via_usb_deconz_already_setup(detect_mock, hass):
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
        "zha", context={"source": SOURCE_USB}, data=discovery_info
    )
    await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "not_zha_device"


@patch("zigpy_znp.zigbee.application.ControllerApplication.probe", return_value=True)
async def test_discovery_via_usb_deconz_ignored(detect_mock, hass):
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
        "zha", context={"source": SOURCE_USB}, data=discovery_info
    )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "confirm"


@patch("zigpy_znp.zigbee.application.ControllerApplication.probe", return_value=True)
async def test_discovery_via_usb_zha_ignored_updates(detect_mock, hass):
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
        "zha", context={"source": SOURCE_USB}, data=discovery_info
    )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_DEVICE] == {
        CONF_DEVICE_PATH: "/dev/ttyZIGBEE",
    }


@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
@patch("zigpy_znp.zigbee.application.ControllerApplication.probe", return_value=True)
async def test_discovery_already_setup(detect_mock, hass):
    """Test zeroconf flow -- radio detected."""
    service_info = zeroconf.ZeroconfServiceInfo(
        host="192.168.1.200",
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
        "zha", context={"source": SOURCE_ZEROCONF}, data=service_info
    )
    await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"


@patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
@patch(
    "homeassistant.components.zha.config_flow.detect_radios",
    return_value={CONF_RADIO_TYPE: "test_radio"},
)
async def test_user_flow(detect_mock, hass):
    """Test user flow -- radio detected."""

    port = com_port()
    port_select = f"{port}, s/n: {port.serial_number} - {port.manufacturer}"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={zigpy.config.CONF_DEVICE_PATH: port_select},
    )
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"].startswith(port.description)
    assert result["data"] == {CONF_RADIO_TYPE: "test_radio"}
    assert detect_mock.await_count == 1
    assert detect_mock.await_args[0][0] == port.device


@patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
@patch(
    "homeassistant.components.zha.config_flow.detect_radios",
    return_value=None,
)
async def test_user_flow_not_detected(detect_mock, hass):
    """Test user flow, radio not detected."""

    port = com_port()
    port_select = f"{port}, s/n: {port.serial_number} - {port.manufacturer}"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={zigpy.config.CONF_DEVICE_PATH: port_select},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "pick_radio"
    assert detect_mock.await_count == 1
    assert detect_mock.await_args[0][0] == port.device


@patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
async def test_user_flow_show_form(hass):
    """Test user step form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"


@patch("serial.tools.list_ports.comports", MagicMock(return_value=[]))
async def test_user_flow_show_manual(hass):
    """Test user flow manual entry when no comport detected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "pick_radio"


async def test_user_flow_manual(hass):
    """Test user flow manual entry."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={zigpy.config.CONF_DEVICE_PATH: config_flow.CONF_MANUAL_PATH},
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "pick_radio"


@pytest.mark.parametrize("radio_type", RadioType.list())
async def test_pick_radio_flow(hass, radio_type):
    """Test radio picker."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: "pick_radio"}, data={CONF_RADIO_TYPE: radio_type}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "port_config"


async def test_user_flow_existing_config_entry(hass):
    """Test if config entry already exists."""
    MockConfigEntry(
        domain=DOMAIN, data={CONF_DEVICE: {CONF_DEVICE_PATH: "/dev/ttyUSB1"}}
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    assert result["type"] == "abort"


@patch("zigpy_znp.zigbee.application.ControllerApplication.probe", return_value=False)
@patch(
    "zigpy_deconz.zigbee.application.ControllerApplication.probe", return_value=False
)
@patch(
    "zigpy_zigate.zigbee.application.ControllerApplication.probe", return_value=False
)
@patch("zigpy_xbee.zigbee.application.ControllerApplication.probe", return_value=False)
async def test_probe_radios(xbee_probe, zigate_probe, deconz_probe, znp_probe, hass):
    """Test detect radios."""
    app_ctrl_cls = MagicMock()
    app_ctrl_cls.SCHEMA_DEVICE = zigpy.config.SCHEMA_DEVICE
    app_ctrl_cls.probe = AsyncMock(side_effect=(True, False))

    p1 = patch(
        "bellows.zigbee.application.ControllerApplication.probe",
        side_effect=(True, False),
    )
    with p1 as probe_mock:
        res = await config_flow.detect_radios("/dev/null")
        assert probe_mock.await_count == 1
        assert znp_probe.await_count == 1  # ZNP appears earlier in the radio list
        assert res[CONF_RADIO_TYPE] == "ezsp"
        assert zigpy.config.CONF_DEVICE in res
        assert (
            res[zigpy.config.CONF_DEVICE][zigpy.config.CONF_DEVICE_PATH] == "/dev/null"
        )

        res = await config_flow.detect_radios("/dev/null")
        assert res is None
        assert xbee_probe.await_count == 1
        assert zigate_probe.await_count == 1
        assert deconz_probe.await_count == 1
        assert znp_probe.await_count == 2


@patch("zigpy_znp.zigbee.application.ControllerApplication.probe", return_value=False)
@patch(
    "zigpy_deconz.zigbee.application.ControllerApplication.probe", return_value=False
)
@patch(
    "zigpy_zigate.zigbee.application.ControllerApplication.probe", return_value=False
)
@patch("zigpy_xbee.zigbee.application.ControllerApplication.probe", return_value=False)
async def test_probe_new_ezsp(xbee_probe, zigate_probe, deconz_probe, znp_probe, hass):
    """Test detect radios."""
    app_ctrl_cls = MagicMock()
    app_ctrl_cls.SCHEMA_DEVICE = zigpy.config.SCHEMA_DEVICE
    app_ctrl_cls.probe = AsyncMock(side_efferct=(True, False))

    p1 = patch(
        "bellows.zigbee.application.ControllerApplication.probe",
        return_value={
            zigpy.config.CONF_DEVICE_PATH: sentinel.usb_port,
            "baudrate": 33840,
        },
    )
    with p1 as probe_mock:
        res = await config_flow.detect_radios("/dev/null")
        assert probe_mock.await_count == 1
        assert res[CONF_RADIO_TYPE] == "ezsp"
        assert zigpy.config.CONF_DEVICE in res
        assert (
            res[zigpy.config.CONF_DEVICE][zigpy.config.CONF_DEVICE_PATH]
            is sentinel.usb_port
        )
        assert res[zigpy.config.CONF_DEVICE]["baudrate"] == 33840


@patch("bellows.zigbee.application.ControllerApplication.probe", return_value=False)
async def test_user_port_config_fail(probe_mock, hass):
    """Test port config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: "pick_radio"},
        data={CONF_RADIO_TYPE: RadioType.ezsp.description},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={zigpy.config.CONF_DEVICE_PATH: "/dev/ttyUSB33"},
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "port_config"
    assert result["errors"]["base"] == "cannot_connect"
    assert probe_mock.await_count == 1


@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
@patch("bellows.zigbee.application.ControllerApplication.probe", return_value=True)
async def test_user_port_config(probe_mock, hass):
    """Test port config."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: "pick_radio"},
        data={CONF_RADIO_TYPE: RadioType.ezsp.description},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={zigpy.config.CONF_DEVICE_PATH: "/dev/ttyUSB33"},
    )

    assert result["type"] == "create_entry"
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
