"""Tests for ZHA config flow."""

import os

from asynctest import mock
import serial.tools.list_ports
import zigpy.config

from homeassistant.components.zha import config_flow
from homeassistant.components.zha.core.const import CONF_RADIO_TYPE, CONTROLLER, DOMAIN

from tests.async_mock import AsyncMock, MagicMock, patch, sentinel
from tests.common import MockConfigEntry


def com_port():
    """Mock of a serial port."""
    port = serial.tools.list_ports_common.ListPortInfo()
    port.serial_number = "1234"
    port.manufacturer = "Virtual serial port"
    port.device = "/dev/ttyUSB1234"
    port.description = "Some serial port"

    return port


@patch(
    "serial.tools.list_ports.comports", return_value=[com_port()]
)
async def test_user_flow(hass):
    """Test user flow."""
    port = com_port()
    port_select = f"{port}, s/n: {port.serial_number} - {port.manufacturer}"

    with mock.patch.object(
        flow, "detect_radios", return_value=mock.sentinel.data,
    ):
        result = await flow.async_step_user(
            user_input={zigpy.config.CONF_DEVICE_PATH: port_select}
        )
    assert result["type"] == "create_entry"
    assert result["title"].startswith(port.description)
    assert result["data"] is mock.sentinel.data

    with mock.patch.object(
        flow, "detect_radios", return_value=None,
    ):
        result = await flow.async_step_user(
            user_input={zigpy.config.CONF_DEVICE_PATH: port_select}
        )

    assert result["type"] == "form"
    assert result["step_id"] == "pick_radio"

    await flow.async_step_user()


async def test_user_flow_manual(hass):
    """Test user flow manual entry."""
    flow = config_flow.ZhaFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(
        user_input={zigpy.config.CONF_DEVICE_PATH: config_flow.CONF_MANUAL_PATH}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "pick_radio"


async def test_pick_radio_flow(hass):
    """Test radio picker."""
    flow = config_flow.ZhaFlowHandler()
    flow.hass = hass

    result = await flow.async_step_pick_radio({CONF_RADIO_TYPE: "ezsp"})
    assert result["type"] == "form"
    assert result["step_id"] == "port_config"

    await flow.async_step_pick_radio()


async def test_user_flow_existing_config_entry(hass):
    """Test if config entry already exists."""
    MockConfigEntry(domain=DOMAIN, data={"usb_path": "/dev/ttyUSB1"}).add_to_hass(hass)
    flow = config_flow.ZhaFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user()

    assert result["type"] == "abort"


async def test_probe_radios(hass):
    """Test detect radios."""
    app_ctrl_cls = mock.MagicMock()
    app_ctrl_cls.SCHEMA_DEVICE = zigpy.config.SCHEMA_DEVICE
    app_ctrl_cls.probe = tests.async_mock.AsyncMock(side_effect=(True, False))

    flow = config_flow.ZhaFlowHandler()
    flow.hass = hass

    with mock.patch.dict(config_flow.RADIO_TYPES, {"ezsp": {CONTROLLER: app_ctrl_cls}}):
        res = await flow.detect_radios("/dev/null")
        assert app_ctrl_cls.probe.await_count == 1
        assert res[CONF_RADIO_TYPE] == "ezsp"
        assert zigpy.config.CONF_DEVICE in res
        assert (
            res[zigpy.config.CONF_DEVICE][zigpy.config.CONF_DEVICE_PATH] == "/dev/null"
        )

        res = await flow.detect_radios("/dev/null")
        assert res is None


async def test_user_port_config_fail(hass):
    """Test port config flow."""
    app_ctrl_cls = mock.MagicMock()
    app_ctrl_cls.SCHEMA_DEVICE = zigpy.config.SCHEMA_DEVICE
    app_ctrl_cls.probe = tests.async_mock.AsyncMock(side_effect=(False, True))

    flow = config_flow.ZhaFlowHandler()
    flow.hass = hass
    await flow.async_step_pick_radio(user_input={CONF_RADIO_TYPE: "ezsp"})

    with mock.patch.dict(config_flow.RADIO_TYPES, {"ezsp": {CONTROLLER: app_ctrl_cls}}):
        result = await flow.async_step_port_config(
            {zigpy.config.CONF_DEVICE_PATH: "/dev/ttyUSB33"}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "port_config"
        assert result["errors"]["base"] == "cannot_connect"

        result = await flow.async_step_port_config(
            {zigpy.config.CONF_DEVICE_PATH: "/dev/ttyUSB33"}
        )
        assert result["type"] == "create_entry"
        assert result["title"].startswith("/dev/ttyUSB33")
        assert (
            result["data"][zigpy.config.CONF_DEVICE][zigpy.config.CONF_DEVICE_PATH]
            == "/dev/ttyUSB33"
        )
        assert result["data"][CONF_RADIO_TYPE] == "ezsp"


def test_get_serial_by_id_no_dir():
    """Test serial by id conversion if there's no /dev/serial/by-id."""
    p1 = mock.patch("os.path.isdir", mock.MagicMock(return_value=False))
    p2 = mock.patch("os.scandir")
    with p1 as is_dir_mock, p2 as scan_mock:
        res = config_flow.get_serial_by_id(mock.sentinel.path)
        assert res is mock.sentinel.path
        assert is_dir_mock.call_count == 1
        assert scan_mock.call_count == 0


def test_get_serial_by_id():
    """Test serial by id conversion."""
    p1 = mock.patch("os.path.isdir", mock.MagicMock(return_value=True))
    p2 = mock.patch("os.scandir")

    def _realpath(path):
        if path is mock.sentinel.matched_link:
            return mock.sentinel.path
        return mock.sentinel.serial_link_path

    p3 = mock.patch("os.path.realpath", side_effect=_realpath)
    with p1 as is_dir_mock, p2 as scan_mock, p3:
        res = config_flow.get_serial_by_id(mock.sentinel.path)
        assert res is mock.sentinel.path
        assert is_dir_mock.call_count == 1
        assert scan_mock.call_count == 1

        entry1 = mock.MagicMock(spec_set=os.DirEntry)
        entry1.is_symlink.return_value = True
        entry1.path = mock.sentinel.some_path

        entry2 = mock.MagicMock(spec_set=os.DirEntry)
        entry2.is_symlink.return_value = False
        entry2.path = mock.sentinel.other_path

        entry3 = mock.MagicMock(spec_set=os.DirEntry)
        entry3.is_symlink.return_value = True
        entry3.path = mock.sentinel.matched_link

        scan_mock.return_value = [entry1, entry2, entry3]
        res = config_flow.get_serial_by_id(mock.sentinel.path)
        assert res is mock.sentinel.matched_link
        assert is_dir_mock.call_count == 2
        assert scan_mock.call_count == 2
