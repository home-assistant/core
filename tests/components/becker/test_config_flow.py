"""Tests for the Becker config flow."""
import os

import pytest
import serial.tools.list_ports

# from tests.async_mock import Mock, MagicMock, patch
# from tests.common import MockConfigEntry
from homeassistant.components.becker import config_flow, const
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_SOURCE
from homeassistant.data_entry_flow import RESULT_TYPE_FORM

from tests.async_mock import MagicMock, patch, sentinel
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
async def test_user_flow(hass):
    """Test user flow."""

    port = com_port()
    port_select = f"{port}, s/n: {port.serial_number} - {port.manufacturer}"

    flow = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={const.CONF_DEVICE_PATH: port_select},
    )
    assert flow["type"] == RESULT_TYPE_FORM
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {const.CONF_DEVICE: port_select}
    )
    print(result)
    assert result["data"] == {const.CONF_DEVICE: port_select}
    # assert result["title"].startswith(port.description)


async def test_user_flow_show_form(hass):
    """Test user step form."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={CONF_SOURCE: SOURCE_USER},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"


@pytest.fixture(name="becker_setup", autouse=True)
def becker_setup_fixture():
    """Mock becker entry setup."""
    with patch("homeassistant.components.becker.async_setup_entry", return_value=True):
        yield


@patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
async def test_user_already_configured(hass):
    """Test duplicated config."""

    MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="aabbccddeeff",
        data={const.CONF_DEVICE: const.DEFAULT_CONF_USB_STICK_PATH},
    ).add_to_hass(hass)

    port = com_port()
    port_select = f"{port}, s/n: {port.serial_number} - {port.manufacturer}"

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={const.CONF_DEVICE: port_select},
    )
    assert result["type"] == "abort"
    assert result["reason"] == "one_instance_only"


async def test_import_with_no_config(hass):
    """Test importing a host without an existing config file."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={"source": "import"},
        data={const.CONF_DEVICE: const.DEFAULT_CONF_USB_STICK_PATH},
    )
    assert result["type"] == "create_entry"
    print(result)
    assert result["data"][const.CONF_DEVICE] == const.DEFAULT_CONF_USB_STICK_PATH


async def test_import_already_configured(hass):
    """Test if a import flow aborts if device is already configured."""
    MockConfigEntry(
        domain="becker",
        unique_id="aabbccddeeff",
        data={"device": const.DEFAULT_CONF_USB_STICK_PATH},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={"source": "import"},
        data={
            const.CONF_DEVICE: const.DEFAULT_CONF_USB_STICK_PATH,
            "properties": {"id": "aa:bb:cc:dd:ee:ff"},
        },
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


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
