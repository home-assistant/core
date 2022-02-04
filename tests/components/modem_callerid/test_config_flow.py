"""Test Modem Caller ID config flow."""
from unittest.mock import AsyncMock, MagicMock, patch

import phone_modem
import serial.tools.list_ports

from homeassistant.components import usb
from homeassistant.components.modem_callerid.const import DOMAIN
from homeassistant.config_entries import SOURCE_USB, SOURCE_USER
from homeassistant.const import CONF_DEVICE, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from . import _patch_config_flow_modem

DISCOVERY_INFO = usb.UsbServiceInfo(
    device=phone_modem.DEFAULT_PORT,
    pid="1340",
    vid="0572",
    serial_number="1234",
    description="modem",
    manufacturer="Connexant",
)


def _patch_setup():
    return patch(
        "homeassistant.components.modem_callerid.async_setup_entry",
        return_value=True,
    )


def com_port():
    """Mock of a serial port."""
    port = serial.tools.list_ports_common.ListPortInfo(phone_modem.DEFAULT_PORT)
    port.serial_number = "1234"
    port.manufacturer = "Virtual serial port"
    port.device = phone_modem.DEFAULT_PORT
    port.description = "Some serial port"

    return port


@patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
async def test_flow_usb(hass: HomeAssistant):
    """Test usb discovery flow."""
    port = com_port()
    with _patch_config_flow_modem(AsyncMock()), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USB},
            data=DISCOVERY_INFO,
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "usb_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICE: phone_modem.DEFAULT_PORT},
        )
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["data"] == {CONF_DEVICE: port.device}


@patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
async def test_flow_usb_cannot_connect(hass: HomeAssistant):
    """Test usb flow connection error."""
    with _patch_config_flow_modem(AsyncMock()) as modemmock:
        modemmock.side_effect = phone_modem.exceptions.SerialError
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_USB}, data=DISCOVERY_INFO
        )
        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == "cannot_connect"


@patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
async def test_flow_user(hass: HomeAssistant):
    """Test user initialized flow."""
    port = com_port()
    port_select = usb.human_readable_device_name(
        port.device,
        port.serial_number,
        port.manufacturer,
        port.description,
        port.vid,
        port.pid,
    )
    mocked_modem = AsyncMock()
    with _patch_config_flow_modem(mocked_modem), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
            data={CONF_DEVICE: port_select},
        )
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["data"] == {CONF_DEVICE: port.device}

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
            data={CONF_DEVICE: port_select},
        )
        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == "no_devices_found"


@patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
async def test_flow_user_error(hass: HomeAssistant):
    """Test user initialized flow with unreachable device."""
    port = com_port()
    port_select = usb.human_readable_device_name(
        port.device,
        port.serial_number,
        port.manufacturer,
        port.description,
        port.vid,
        port.pid,
    )
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


@patch("serial.tools.list_ports.comports", MagicMock())
async def test_flow_user_no_port_list(hass: HomeAssistant):
    """Test user with no list of ports."""
    with _patch_config_flow_modem(AsyncMock()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
            data={CONF_DEVICE: phone_modem.DEFAULT_PORT},
        )
        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == "no_devices_found"


async def test_abort_user_with_existing_flow(hass: HomeAssistant):
    """Test user flow is aborted when another discovery has happened."""
    with _patch_config_flow_modem(AsyncMock()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USB},
            data=DISCOVERY_INFO,
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "usb_confirm"

        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
            data={},
        )

        assert result2["type"] == RESULT_TYPE_ABORT
        assert result2["reason"] == "already_in_progress"
