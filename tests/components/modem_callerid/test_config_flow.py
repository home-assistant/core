"""Test Modem Caller ID config flow."""
from unittest.mock import MagicMock, patch

import phone_modem

from homeassistant import data_entry_flow
from homeassistant.components import usb
from homeassistant.components.modem_callerid.const import DOMAIN
from homeassistant.config_entries import SOURCE_USB, SOURCE_USER
from homeassistant.const import CONF_DEVICE, CONF_SOURCE
from homeassistant.core import HomeAssistant

from . import com_port, patch_config_flow_modem

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
    )


@patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
async def test_flow_usb(hass: HomeAssistant):
    """Test usb discovery flow."""
    with patch_config_flow_modem(), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USB},
            data=DISCOVERY_INFO,
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "usb_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICE: phone_modem.DEFAULT_PORT},
        )
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["data"] == {CONF_DEVICE: com_port().device}


@patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
async def test_flow_usb_cannot_connect(hass: HomeAssistant):
    """Test usb flow connection error."""
    with patch_config_flow_modem() as modemmock:
        modemmock.side_effect = phone_modem.exceptions.SerialError
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_USB}, data=DISCOVERY_INFO
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
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
    with patch_config_flow_modem(), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
            data={CONF_DEVICE: port_select},
        )
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["data"] == {CONF_DEVICE: port.device}

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
            data={CONF_DEVICE: port_select},
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
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
    with patch_config_flow_modem() as modemmock:
        modemmock.side_effect = phone_modem.exceptions.SerialError
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data={CONF_DEVICE: port_select}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}

        modemmock.side_effect = None
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICE: port_select},
        )
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["data"] == {CONF_DEVICE: port.device}


@patch("serial.tools.list_ports.comports", MagicMock())
async def test_flow_user_no_port_list(hass: HomeAssistant):
    """Test user with no list of ports."""
    with patch_config_flow_modem():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
            data={CONF_DEVICE: phone_modem.DEFAULT_PORT},
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "no_devices_found"


async def test_abort_user_with_existing_flow(hass: HomeAssistant):
    """Test user flow is aborted when another discovery has happened."""
    with patch_config_flow_modem():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USB},
            data=DISCOVERY_INFO,
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "usb_confirm"

        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
            data={},
        )

        assert result2["type"] == data_entry_flow.FlowResultType.ABORT
        assert result2["reason"] == "already_in_progress"
