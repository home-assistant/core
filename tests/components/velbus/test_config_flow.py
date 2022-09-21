"""Tests for the Velbus config flow."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import serial.tools.list_ports
from velbusaio.exceptions import VelbusConnectionFailed

from homeassistant import data_entry_flow
from homeassistant.components import usb
from homeassistant.components.velbus import config_flow
from homeassistant.components.velbus.const import DOMAIN
from homeassistant.config_entries import SOURCE_USB
from homeassistant.const import CONF_NAME, CONF_PORT, CONF_SOURCE
from homeassistant.core import HomeAssistant

from .const import PORT_SERIAL, PORT_TCP

from tests.common import MockConfigEntry

DISCOVERY_INFO = usb.UsbServiceInfo(
    device=PORT_SERIAL,
    pid="10CF",
    vid="0B1B",
    serial_number="1234",
    description="Velbus VMB1USB",
    manufacturer="Velleman",
)


def com_port():
    """Mock of a serial port."""
    port = serial.tools.list_ports_common.ListPortInfo(PORT_SERIAL)
    port.serial_number = "1234"
    port.manufacturer = "Virtual serial port"
    port.device = PORT_SERIAL
    port.description = "Some serial port"
    return port


@pytest.fixture(autouse=True)
def override_async_setup_entry() -> AsyncMock:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.velbus.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="controller_connection_failed")
def mock_controller_connection_failed():
    """Mock the velbus controller with an assert."""
    with patch("velbusaio.controller.Velbus", side_effect=VelbusConnectionFailed()):
        yield


def init_config_flow(hass: HomeAssistant):
    """Init a configuration flow."""
    flow = config_flow.VelbusConfigFlow()
    flow.hass = hass
    return flow


@pytest.mark.usefixtures("controller")
async def test_user(hass: HomeAssistant):
    """Test user config."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await flow.async_step_user(
        {CONF_NAME: "Velbus Test Serial", CONF_PORT: PORT_SERIAL}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "velbus_test_serial"
    assert result["data"][CONF_PORT] == PORT_SERIAL

    result = await flow.async_step_user(
        {CONF_NAME: "Velbus Test TCP", CONF_PORT: PORT_TCP}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "velbus_test_tcp"
    assert result["data"][CONF_PORT] == PORT_TCP


@pytest.mark.usefixtures("controller_connection_failed")
async def test_user_fail(hass: HomeAssistant):
    """Test user config."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user(
        {CONF_NAME: "Velbus Test Serial", CONF_PORT: PORT_SERIAL}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {CONF_PORT: "cannot_connect"}

    result = await flow.async_step_user(
        {CONF_NAME: "Velbus Test TCP", CONF_PORT: PORT_TCP}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {CONF_PORT: "cannot_connect"}


@pytest.mark.usefixtures("config_entry")
async def test_abort_if_already_setup(hass: HomeAssistant):
    """Test we abort if Velbus is already setup."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user({CONF_PORT: PORT_TCP, CONF_NAME: "velbus test"})
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"port": "already_configured"}


@pytest.mark.usefixtures("controller")
@patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
async def test_flow_usb(hass: HomeAssistant):
    """Test usb discovery flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USB},
        data=DISCOVERY_INFO,
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    # test an already configured discovery
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PORT: PORT_SERIAL},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USB},
        data=DISCOVERY_INFO,
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("controller_connection_failed")
@patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
async def test_flow_usb_failed(hass: HomeAssistant):
    """Test usb discovery flow with a failed velbus test."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USB},
        data=DISCOVERY_INFO,
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
