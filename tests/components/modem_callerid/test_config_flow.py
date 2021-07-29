"""Test Modem Caller ID config flow."""
import os
from unittest.mock import AsyncMock, MagicMock, patch, sentinel

import phone_modem
import serial.tools.list_ports

from homeassistant.components.modem_callerid import config_flow
from homeassistant.components.modem_callerid.const import DEFAULT_NAME, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_DEVICE, CONF_SOURCE
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from . import CONF_DATA, IMPORT_DATA, _patch_config_flow_modem

from tests.common import MockConfigEntry


def _patch_setup():
    return patch(
        "homeassistant.components.modem_callerid.async_setup_entry",
        return_value=True,
    )


def com_port():
    """Mock of a serial port."""
    port = serial.tools.list_ports_common.ListPortInfo("/dev/ttyUSB1234")
    port.serial_number = "1234"
    port.manufacturer = "Virtual serial port"
    port.device = "/dev/ttyUSB1234"
    port.description = "Some serial port"

    return port


@patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
async def test_flow_user(hass):
    """Test user initialized flow."""
    port = com_port()
    port_select = f"{port}, s/n: {port.serial_number} - {port.manufacturer}"
    mocked_modem = AsyncMock()
    with _patch_config_flow_modem(mocked_modem), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
            data={CONF_DEVICE: port_select},
        )
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["data"] == {CONF_DEVICE: port.device}


@patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
async def test_flow_user_error(hass):
    """Test user initialized flow with unreachable device."""
    port = com_port()
    port_select = f"{port}, s/n: {port.serial_number} - {port.manufacturer}"
    with _patch_config_flow_modem(AsyncMock()) as modemmock:
        modemmock.side_effect = phone_modem.exceptions.SerialError
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data={CONF_DEVICE: port_select}
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}

        modemmock.side_effect = None
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICE: port_select},
        )
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["data"] == {CONF_DEVICE: port.device}


async def test_flow_user_manual(hass):
    """Test user flow manual entry."""
    mocked_modem = AsyncMock()
    with _patch_config_flow_modem(mocked_modem), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
            data={CONF_DEVICE: config_flow.CONF_MANUAL_PATH},
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "user_manual"


@patch("serial.tools.list_ports.comports", MagicMock())
async def test_flow_user_no_port_list(hass):
    """Test user with no list of ports."""
    with _patch_config_flow_modem(AsyncMock()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
            data={CONF_DEVICE: phone_modem.DEFAULT_PORT},
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "user_manual"
        assert result["errors"] == {}


async def test_flow_import(hass):
    """Test import step."""
    with _patch_config_flow_modem(AsyncMock()), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_IMPORT}, data=IMPORT_DATA
        )

        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == DEFAULT_NAME
        assert result["data"] == CONF_DATA


async def test_flow_import_duplicate(hass):
    """Test already configured import."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: phone_modem.DEFAULT_PORT},
    )

    entry.add_to_hass(hass)

    service_info = {CONF_DEVICE: phone_modem.DEFAULT_PORT}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_IMPORT}, data=service_info
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


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
