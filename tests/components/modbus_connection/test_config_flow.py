"""Tests for the Modbus Connection config flow."""

from typing import Any
from unittest.mock import AsyncMock

from modbus_connection import ModbusConnectionError
from modbus_connection.mock import MockModbusConnection
import pytest

from homeassistant.components.modbus_connection.const import (
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_PARITY,
    CONF_STOPBITS,
    CONNECTION_SERIAL,
    CONNECTION_TCP,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

SERIAL_INPUT = {
    CONF_DEVICE: "/dev/ttyUSB0",
    CONF_BAUDRATE: 9600,
    CONF_PARITY: "N",
    CONF_STOPBITS: 1,
    CONF_BYTESIZE: 8,
}


async def _start_menu(hass: HomeAssistant, step: str) -> str:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert set(result["menu_options"]) == {"network", "serial"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": step}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == step
    return result["flow_id"]


@pytest.mark.usefixtures("mock_connect", "mock_setup_entry")
async def test_network_flow(hass: HomeAssistant) -> None:
    """The network step opens the connection and creates an entry."""
    flow_id = await _start_menu(hass, "network")
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_HOST: "1.2.3.4", CONF_PORT: 502}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_TYPE: CONNECTION_TCP,
        CONF_HOST: "1.2.3.4",
        CONF_PORT: 502,
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_network_cannot_connect_then_recovers(
    hass: HomeAssistant,
    mock_connect: AsyncMock,
    mock_modbus_connection: MockModbusConnection,
) -> None:
    """A failed probe shows an error; a later success creates the entry."""
    flow_id = await _start_menu(hass, "network")
    mock_connect.side_effect = ModbusConnectionError("nope")
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_HOST: "1.2.3.4", CONF_PORT: 502}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_connect.side_effect = None
    mock_connect.return_value = mock_modbus_connection
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "1.2.3.4", CONF_PORT: 502}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_connect", "mock_setup_entry")
async def test_serial_flow(hass: HomeAssistant) -> None:
    """The serial step opens the connection and creates a serial entry."""
    flow_id = await _start_menu(hass, "serial")
    result = await hass.config_entries.flow.async_configure(flow_id, SERIAL_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_TYPE: CONNECTION_SERIAL, **SERIAL_INPUT}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_serial_cannot_open(hass: HomeAssistant, mock_connect: AsyncMock) -> None:
    """A failed serial open shows the serial-specific error."""
    flow_id = await _start_menu(hass, "serial")
    mock_connect.side_effect = ModbusConnectionError("nope")
    result = await hass.config_entries.flow.async_configure(flow_id, SERIAL_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_open_serial_port"}


@pytest.mark.parametrize(
    ("step", "data", "user_input"),
    [
        pytest.param(
            "network",
            {CONF_TYPE: CONNECTION_TCP, CONF_HOST: "1.2.3.4", CONF_PORT: 502},
            {CONF_HOST: "1.2.3.4", CONF_PORT: 502},
            id="network",
        ),
        pytest.param(
            "serial",
            {CONF_TYPE: CONNECTION_SERIAL, **SERIAL_INPUT},
            SERIAL_INPUT,
            id="serial",
        ),
    ],
)
async def test_duplicate_aborts(
    hass: HomeAssistant,
    step: str,
    data: dict[str, Any],
    user_input: dict[str, Any],
) -> None:
    """Re-adding an already-configured link aborts before opening it.

    The dedupe runs before opening the connection, so no connect is needed.
    """
    MockConfigEntry(domain=DOMAIN, data=data).add_to_hass(hass)

    flow_id = await _start_menu(hass, step)
    result = await hass.config_entries.flow.async_configure(flow_id, user_input)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
