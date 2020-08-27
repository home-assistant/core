"""Tests for ZHA config flow."""

import os

import pytest
import serial.tools.list_ports
import zigpy.config

from homeassistant import setup
from homeassistant.components.zha import config_flow
from homeassistant.components.zha.core.const import CONF_RADIO_TYPE, DOMAIN, RadioType
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_SOURCE
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM

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


async def test_user_flow_show_form(hass):
    """Test user step form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"


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
    MockConfigEntry(domain=DOMAIN, data={"usb_path": "/dev/ttyUSB1"}).add_to_hass(hass)
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    assert result["type"] == "abort"


@patch("zigpy_cc.zigbee.application.ControllerApplication.probe", return_value=False)
@patch(
    "zigpy_deconz.zigbee.application.ControllerApplication.probe", return_value=False
)
@patch(
    "zigpy_zigate.zigbee.application.ControllerApplication.probe", return_value=False
)
@patch("zigpy_xbee.zigbee.application.ControllerApplication.probe", return_value=False)
async def test_probe_radios(xbee_probe, zigate_probe, deconz_probe, cc_probe, hass):
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
        assert cc_probe.await_count == 1


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
    await setup.async_setup_component(hass, "persistent_notification", {})

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


def test_get_serial_by_id_no_dir():
    """Test serial by id conversion if there's no /dev/serial/by-id."""
    p1 = patch("os.path.isdir", MagicMock(return_value=False))
    p2 = patch("os.scandir")
    with p1 as is_dir_mock, p2 as scan_mock:
        res = config_flow.get_serial_by_id(sentinel.path)
        assert res is sentinel.path
        assert is_dir_mock.call_count == 1
        assert scan_mock.call_count == 0


def test_get_serial_by_id():
    """Test serial by id conversion."""
    p1 = patch("os.path.isdir", MagicMock(return_value=True))
    p2 = patch("os.scandir")

    def _realpath(path):
        if path is sentinel.matched_link:
            return sentinel.path
        return sentinel.serial_link_path

    p3 = patch("os.path.realpath", side_effect=_realpath)
    with p1 as is_dir_mock, p2 as scan_mock, p3:
        res = config_flow.get_serial_by_id(sentinel.path)
        assert res is sentinel.path
        assert is_dir_mock.call_count == 1
        assert scan_mock.call_count == 1

        entry1 = MagicMock(spec_set=os.DirEntry)
        entry1.is_symlink.return_value = True
        entry1.path = sentinel.some_path

        entry2 = MagicMock(spec_set=os.DirEntry)
        entry2.is_symlink.return_value = False
        entry2.path = sentinel.other_path

        entry3 = MagicMock(spec_set=os.DirEntry)
        entry3.is_symlink.return_value = True
        entry3.path = sentinel.matched_link

        scan_mock.return_value = [entry1, entry2, entry3]
        res = config_flow.get_serial_by_id(sentinel.path)
        assert res is sentinel.matched_link
        assert is_dir_mock.call_count == 2
        assert scan_mock.call_count == 2
