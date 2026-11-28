"""Tests for the WAFE config flow."""

from unittest.mock import MagicMock

from modbus_connection import ModbusTcpParams, ModbusTimeoutError
from modbus_connection.mock import MockModbusUnit
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.wafe.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError

from . import MOCK_ENTRY_DATA, MOCK_HOST, MOCK_TITLE, MOCK_UNIT_ID


async def _start_user_flow(hass: HomeAssistant) -> str:
    """Open the user flow and return its ID."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    return result["flow_id"]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow(hass: HomeAssistant, mock_temporary_unit: MagicMock) -> None:
    """Test a unit set up from the user flow."""
    flow_id = await _start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_HOST: MOCK_HOST, CONF_PORT: 1502}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_TITLE
    assert result["data"] == {CONF_HOST: MOCK_HOST, CONF_PORT: 1502}
    assert result["result"].unique_id == MOCK_UNIT_ID
    assert mock_temporary_unit.call_args.args[1:] == (
        ModbusTcpParams(host=MOCK_HOST, port=1502),
        1,
    )


@pytest.mark.usefixtures("mock_setup_entry", "mock_temporary_unit")
async def test_user_flow_unknown_model(
    hass: HomeAssistant, mock_unit: MockModbusUnit
) -> None:
    """Test an unknown model is named after the manufacturer alone."""
    mock_unit.input[1001] = 99
    flow_id = await _start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(flow_id, MOCK_ENTRY_DATA)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "WAFE"
    assert result["result"].unique_id == MOCK_UNIT_ID


@pytest.mark.usefixtures("mock_setup_entry", "mock_temporary_unit")
async def test_user_flow_cannot_connect_recovers(
    hass: HomeAssistant, mock_unit: MockModbusUnit
) -> None:
    """Test a silent unit shows an error and the flow recovers."""
    mock_unit.fail_requests(ModbusTimeoutError())
    flow_id = await _start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(flow_id, MOCK_ENTRY_DATA)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_unit.fail_requests(None)
    result = await hass.config_entries.flow.async_configure(flow_id, MOCK_ENTRY_DATA)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MOCK_UNIT_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_device_in_use_recovers(
    hass: HomeAssistant,
    mock_temporary_unit: MagicMock,
) -> None:
    """Test a unit already used over other link settings shows an error."""
    working = mock_temporary_unit.side_effect
    mock_temporary_unit.side_effect = HomeAssistantError("in use")
    flow_id = await _start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(flow_id, MOCK_ENTRY_DATA)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_temporary_unit.side_effect = working
    result = await hass.config_entries.flow.async_configure(flow_id, MOCK_ENTRY_DATA)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MOCK_UNIT_ID


@pytest.mark.usefixtures("mock_setup_entry", "mock_temporary_unit")
async def test_user_flow_unit_without_id(
    hass: HomeAssistant, mock_unit: MockModbusUnit
) -> None:
    """Test a unit that reports no ID is refused."""
    mock_unit.input[1000] = 0
    flow_id = await _start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(flow_id, MOCK_ENTRY_DATA)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_unit_id"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_same_address_aborts_before_probing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_temporary_unit: MagicMock,
) -> None:
    """Test a configured address aborts without connecting to the unit."""
    mock_config_entry.add_to_hass(hass)
    flow_id = await _start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(flow_id, MOCK_ENTRY_DATA)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_temporary_unit.assert_not_called()


@pytest.mark.usefixtures("mock_setup_entry", "mock_temporary_unit")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the same unit reached under another name is recognized by its ID."""
    mock_config_entry.add_to_hass(hass)
    flow_id = await _start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_HOST: "wafe.local", CONF_PORT: 502}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
