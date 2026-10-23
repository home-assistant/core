"""Tests for the aerosmart config flow."""

from typing import cast
from unittest.mock import AsyncMock, patch

from modbus_connection import ModbusConnectionError
from modbus_connection.mock import MockModbusUnit
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.aerosmart.const import (
    CONF_BAUDRATE,
    CONF_UNIT_HEAT_PUMP,
    CONF_UNIT_VENTILATION,
    DOMAIN,
    TYPE_SERIAL,
    TYPE_TCP,
)
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MockModbusApi


async def _start_flow(hass: HomeAssistant, connection_type: str) -> str:
    """Open the config flow and select a connection type."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == [TYPE_TCP, TYPE_SERIAL]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": connection_type}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == connection_type
    return result["flow_id"]


@pytest.mark.usefixtures("mock_modbus_unit_ventilation", "mock_modbus_unit_heat_pump")
async def test_full_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_modbus_unit_ventilation: MockModbusUnit,
    mock_modbus_unit_heat_pump: MockModbusUnit,
) -> None:
    """A valid connection and both unit IDs create an entry."""
    flow_id = await _start_flow(hass, TYPE_TCP)
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            CONF_HOST: "  GATEWAY.local  ",
            CONF_PORT: 8899,
            CONF_UNIT_VENTILATION: 1,
            CONF_UNIT_HEAT_PUMP: 2,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "aerosmart"
    assert result["data"] == {
        CONF_TYPE: TYPE_TCP,
        CONF_HOST: "gateway.local",
        CONF_PORT: 8899,
        CONF_UNIT_VENTILATION: 1,
        CONF_UNIT_HEAT_PUMP: 2,
    }
    assert result["result"].unique_id is None
    mock_setup_entry.assert_called_once()
    assert mock_modbus_unit_ventilation.message_spacing == 0.3
    assert mock_modbus_unit_heat_pump.message_spacing == 0.3
    assert mock_modbus_unit_ventilation.required_connect_delay == 1.0
    assert mock_modbus_unit_heat_pump.required_connect_delay == 1.0


@pytest.mark.usefixtures("mock_modbus_unit_ventilation", "mock_modbus_unit_heat_pump")
async def test_same_unit_ids(
    hass: HomeAssistant,
    mock_modbus_api: MockModbusApi,
    mock_setup_entry: AsyncMock,
) -> None:
    """Using the same unit ID for both controllers is rejected before probing."""
    flow_id = await _start_flow(hass, TYPE_TCP)
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 502,
            CONF_UNIT_VENTILATION: 1,
            CONF_UNIT_HEAT_PUMP: 1,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "same_unit"}
    mock_modbus_api.temporary_unit.assert_not_called()
    mock_setup_entry.assert_not_called()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 502,
            CONF_UNIT_VENTILATION: 1,
            CONF_UNIT_HEAT_PUMP: 2,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_setup_entry.assert_called_once()


@pytest.mark.usefixtures("mock_modbus_unit_ventilation", "mock_modbus_unit_heat_pump")
async def test_cannot_connect(
    hass: HomeAssistant,
    mock_modbus_api: MockModbusApi,
    mock_setup_entry: AsyncMock,
) -> None:
    """An unreachable unit shows a form error instead of aborting."""
    working_side_effect = mock_modbus_api.temporary_unit.side_effect
    mock_modbus_api.temporary_unit.side_effect = OSError("unreachable")

    flow_id = await _start_flow(hass, TYPE_TCP)
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 502,
            CONF_UNIT_VENTILATION: 1,
            CONF_UNIT_HEAT_PUMP: 2,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_modbus_api.temporary_unit.side_effect = working_side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 502,
            CONF_UNIT_VENTILATION: 1,
            CONF_UNIT_HEAT_PUMP: 2,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_setup_entry.assert_called_once()


@pytest.mark.parametrize(
    "unit_fixture",
    [
        pytest.param("mock_modbus_unit_ventilation", id="ventilation"),
        pytest.param("mock_modbus_unit_heat_pump", id="heat-pump"),
    ],
)
@pytest.mark.usefixtures("mock_modbus_unit_ventilation", "mock_modbus_unit_heat_pump")
async def test_controller_read_failure(
    hass: HomeAssistant,
    request: pytest.FixtureRequest,
    mock_modbus_api: MockModbusApi,
    mock_setup_entry: AsyncMock,
    unit_fixture: str,
) -> None:
    """A read failure from either controller shows a connection error."""
    unit = cast(MockModbusUnit, request.getfixturevalue(unit_fixture))
    unit.fail_requests(ModbusConnectionError("simulated read failure"))

    flow_id = await _start_flow(hass, TYPE_TCP)
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 502,
            CONF_UNIT_VENTILATION: 1,
            CONF_UNIT_HEAT_PUMP: 2,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert mock_modbus_api.temporary_unit.call_count == 2
    mock_setup_entry.assert_not_called()

    unit.fail_requests(None)
    with patch(
        "homeassistant.components.aerosmart.config_flow."
        "AerosmartConfigFlow._async_can_connect",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.2.3.4",
                CONF_PORT: 502,
                CONF_UNIT_VENTILATION: 1,
                CONF_UNIT_HEAT_PUMP: 2,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_setup_entry.assert_called_once()


@pytest.mark.usefixtures("mock_modbus_unit_ventilation", "mock_modbus_unit_heat_pump")
async def test_duplicate_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The same connection and both unit IDs abort as already configured."""
    mock_config_entry.add_to_hass(hass)

    flow_id = await _start_flow(hass, TYPE_TCP)
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 502,
            CONF_UNIT_VENTILATION: 1,
            CONF_UNIT_HEAT_PUMP: 2,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_modbus_unit_ventilation", "mock_modbus_unit_heat_pump")
async def test_serial_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_modbus_api: MockModbusApi,
) -> None:
    """A serial port selected through serialx can create an entry."""
    flow_id = await _start_flow(hass, TYPE_SERIAL)

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            CONF_DEVICE: "/dev/ttyUSB0",
            CONF_BAUDRATE: 19200,
            CONF_UNIT_VENTILATION: 1,
            CONF_UNIT_HEAT_PUMP: 2,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_TYPE: TYPE_SERIAL,
        CONF_DEVICE: "/dev/ttyUSB0",
        CONF_BAUDRATE: 19200,
        CONF_UNIT_VENTILATION: 1,
        CONF_UNIT_HEAT_PUMP: 2,
    }
    assert mock_modbus_api.temporary_unit.call_count == 2
    mock_setup_entry.assert_called_once()
