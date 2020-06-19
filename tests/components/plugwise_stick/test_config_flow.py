"""Test the Plugwise USB-stick config flow."""

import os

from plugwise.exceptions import NetworkDown, StickInitError, TimeoutException
import serial.tools.list_ports

from homeassistant.components.plugwise_stick import config_flow
from homeassistant.components.plugwise_stick.const import CONF_USB_PATH, DOMAIN
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
    port.device = "/dev/ttyUSB1"
    port.description = "Some serial port"
    return port


async def test_user_flow_show_form(hass):
    """Test user step form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER},
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"


@patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
@patch(
    "homeassistant.components.plugwise_stick.config_flow.validate_connection",
    AsyncMock(return_value=None),
)
async def test_user_flow_select(hass):
    """Test user flow when USB-stick is selected from list."""
    port = com_port()
    port_select = f"{port}, s/n: {port.serial_number} - {port.manufacturer}"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data={CONF_USB_PATH: port_select},
    )
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {CONF_USB_PATH: "/dev/ttyUSB1"}


async def test_user_flow_manual_selected_show_form(hass):
    """Test user step form when manual path is selected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={CONF_USB_PATH: config_flow.CONF_MANUAL_PATH},
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "manual_path"


@patch(
    "homeassistant.components.plugwise_stick.config_flow.validate_connection",
    AsyncMock(return_value=None),
)
async def test_user_flow_manual(hass):
    """Test user flow when USB-stick is manually entered."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={CONF_USB_PATH: config_flow.CONF_MANUAL_PATH},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USB_PATH: "/dev/ttyUSB2"},
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {CONF_USB_PATH: "/dev/ttyUSB2"}


async def test_invalid_connection(hass):
    """Test invalid connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data={CONF_USB_PATH: "/dev/null"},
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_empty_connection(hass):
    """Test empty connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data={CONF_USB_PATH: None},
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "connection_failed"}


async def test_existing_connection(hass):
    """Test existing connection."""
    MockConfigEntry(domain=DOMAIN, data={CONF_USB_PATH: "/dev/ttyUSB3"}).add_to_hass(
        hass
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={CONF_USB_PATH: "/dev/ttyUSB3"},
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "connection_exists"}


@patch("plugwise.stick.connect", MagicMock(return_value=None))
@patch("plugwise.stick.initialize_stick", MagicMock(side_effect=(StickInitError)))
async def test_failed_initialization(hass):
    """Test we handle failed initialization of Plugwise USB-stick."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data={CONF_USB_PATH: "/dev/null"},
    )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "stick_init"}


@patch("plugwise.stick.connect", MagicMock(return_value=None))
@patch("plugwise.stick.initialize_stick", MagicMock(side_effect=(NetworkDown)))
async def test_network_down_exception(hass):
    """Test we handle network_down exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data={CONF_USB_PATH: "/dev/null"},
    )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "network_down"}


@patch("plugwise.stick.connect", MagicMock(return_value=None))
@patch("plugwise.stick.initialize_stick", MagicMock(side_effect=(TimeoutException)))
async def test_timeout_exception(hass):
    """Test we handle time exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data={CONF_USB_PATH: "/dev/null"},
    )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "network_timeout"}


@patch("plugwise.stick.connect", MagicMock(return_value=None))
@patch("plugwise.stick.initialize_stick", MagicMock(return_value=None))
@patch("plugwise.stick.disconnect", MagicMock(return_value=None))
async def test_successful_connection(hass):
    """Test successful connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data={CONF_USB_PATH: "/dev/null"},
    )
    assert result["errors"] == {}


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
