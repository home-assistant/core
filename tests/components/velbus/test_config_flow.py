"""Tests for the Velbus config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import serial.tools.list_ports
from velbusaio.exceptions import VelbusConnectionFailed

from homeassistant.components.velbus.const import CONF_TLS, DOMAIN
from homeassistant.config_entries import SOURCE_USB, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from .const import PORT_SERIAL

from tests.common import MockConfigEntry

DISCOVERY_INFO = UsbServiceInfo(
    device=PORT_SERIAL,
    pid="10CF",
    vid="0B1B",
    serial_number="1234",
    description="Velbus VMB1USB",
    manufacturer="Velleman",
)

USB_DEV = "/dev/ttyACME100 - Some serial port, s/n: 1234 - Virtual serial port"


def com_port():
    """Mock of a serial port."""
    port = serial.tools.list_ports_common.ListPortInfo(PORT_SERIAL)
    port.serial_number = "1234"
    port.manufacturer = "Virtual serial port"
    port.device = PORT_SERIAL
    port.description = "Some serial port"
    return port


@pytest.fixture(autouse=True)
def override_async_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with (
        patch(
            "homeassistant.components.velbus.async_setup_entry", return_value=True
        ) as mock,
    ):
        yield mock


@pytest.fixture(name="controller_connection_failed")
def mock_controller_connection_failed():
    """Mock the velbus controller with an assert."""
    with patch("velbusaio.controller.Velbus", side_effect=VelbusConnectionFailed()):
        yield


@pytest.mark.usefixtures("controller")
@pytest.mark.parametrize(
    ("inputParams", "expected"),
    [
        (
            {
                CONF_TLS: True,
                CONF_PASSWORD: "password",
            },
            "tls://password@velbus:6000",
        ),
        (
            {
                CONF_TLS: True,
                CONF_PASSWORD: "",
            },
            "tls://velbus:6000",
        ),
        ({CONF_TLS: True}, "tls://velbus:6000"),
        ({CONF_TLS: False}, "velbus:6000"),
    ],
)
async def test_user_network_succes(
    hass: HomeAssistant, inputParams: str, expected: str
) -> None:
    """Test user network config."""
    # inttial menu show
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result
    assert result.get("flow_id")
    assert result.get("type") is FlowResultType.MENU
    assert result.get("step_id") == "user"
    assert result.get("menu_options") == ["network", "usbselect"]
    # select the network option
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        {"next_step_id": "network"},
    )
    assert result["type"] is FlowResultType.FORM
    # fill in the network form
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        {
            CONF_HOST: "velbus",
            CONF_PORT: 6000,
            **inputParams,
        },
    )
    assert result
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "Velbus Network"
    data = result.get("data")
    assert data
    assert data[CONF_PORT] == expected


@pytest.mark.usefixtures("controller")
@patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
async def test_user_usb_succes(hass: HomeAssistant) -> None:
    """Test user usb step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        {"next_step_id": "usbselect"},
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PORT: USB_DEV,
        },
    )
    assert result
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "Velbus USB"
    data = result.get("data")
    assert data
    assert data[CONF_PORT] == PORT_SERIAL


@pytest.mark.usefixtures("controller")
async def test_network_abort_if_already_setup(hass: HomeAssistant) -> None:
    """Test we abort if Velbus is already setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PORT: "127.0.0.1:3788"},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        {"next_step_id": "network"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TLS: False,
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 3788,
            CONF_PASSWORD: "",
        },
    )
    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


@pytest.mark.usefixtures("controller")
@patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
async def test_flow_usb(hass: HomeAssistant) -> None:
    """Test usb discovery flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USB},
        data=DISCOVERY_INFO,
    )
    assert result
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result
    assert result["result"].unique_id == "1234"
    assert result.get("type") is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("controller")
@patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
async def test_flow_usb_if_already_setup(hass: HomeAssistant) -> None:
    """Test we abort if Velbus USB discovbery aborts in case it is already setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PORT: PORT_SERIAL},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"),
        {"next_step_id": "usbselect"},
    )
    assert result
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PORT: USB_DEV,
        },
    )
    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


@pytest.mark.usefixtures("controller_connection_failed")
@patch("serial.tools.list_ports.comports", MagicMock(return_value=[com_port()]))
async def test_flow_usb_failed(hass: HomeAssistant) -> None:
    """Test usb discovery flow with a failed velbus test."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USB},
        data=DISCOVERY_INFO,
    )
    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "cannot_connect"
