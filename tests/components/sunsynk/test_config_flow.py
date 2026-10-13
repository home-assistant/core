"""Test the Sunsynk config flow."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

from modbus_connection import ModbusTcpParams, ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest
from sunsynk.exceptions import SunsynkAuthenticationError, SunsynkConnectionError

from homeassistant.components.sunsynk.const import DOMAIN, TYPE_CLOUD, TYPE_MODBUS
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_TYPE, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .conftest import (
    MODBUS_SERIAL_NUMBER,
    MODBUS_USER_INPUT,
    PASSWORD,
    USER_ID,
    USERNAME,
)

from tests.common import MockConfigEntry

DHCP_SERVICE_INFO = DhcpServiceInfo(
    hostname="e-linter", ip="192.168.1.20", macaddress="1091a8aabbcc"
)


async def _async_start_flow(hass: HomeAssistant, step: str) -> FlowResult:
    """Start a user flow and select a connection type from the menu."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": step}
    )


async def test_full_cloud_flow(
    hass: HomeAssistant,
    mock_sunsynk_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the full flow for a Sunsynk Connect account."""
    result = await _async_start_flow(hass, TYPE_CLOUD)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == TYPE_CLOUD
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == USERNAME
    assert result["data"] == {
        CONF_TYPE: TYPE_CLOUD,
        CONF_USERNAME: USERNAME,
        CONF_PASSWORD: PASSWORD,
    }
    assert result["result"].unique_id == USER_ID
    assert len(mock_sunsynk_client.get_user.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_sunsynk_client", "mock_setup_entry")
async def test_duplicate_cloud_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the flow aborts when the account is already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await _async_start_flow(hass, TYPE_CLOUD)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: "other@example.com", CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        pytest.param(SunsynkAuthenticationError, "invalid_auth", id="invalid_auth"),
        pytest.param(SunsynkConnectionError, "cannot_connect", id="cannot_connect"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_cloud_flow_errors(
    hass: HomeAssistant,
    mock_sunsynk_client: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test the cloud flow shows an error and can recover."""
    mock_sunsynk_client.get_user.side_effect = exception
    result = await _async_start_flow(hass, TYPE_CLOUD)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_sunsynk_client.get_user.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_modbus_connection_class")
async def test_full_modbus_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_modbus_connection: MockModbusConnection,
) -> None:
    """Test the full flow for an inverter that uses Modbus."""
    result = await _async_start_flow(hass, TYPE_MODBUS)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == TYPE_MODBUS
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MODBUS_USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Inverter {MODBUS_SERIAL_NUMBER}"
    assert result["data"] == {CONF_TYPE: TYPE_MODBUS, **MODBUS_USER_INPUT}
    assert result["result"].unique_id == MODBUS_SERIAL_NUMBER
    assert len(mock_setup_entry.mock_calls) == 1
    # The flow closes its temporary connection.
    assert mock_modbus_connection.connected is False


@pytest.mark.usefixtures("mock_modbus_connection_class", "mock_setup_entry")
async def test_duplicate_modbus_entry(
    hass: HomeAssistant, mock_modbus_config_entry: MockConfigEntry
) -> None:
    """Test the flow aborts when the inverter is already configured."""
    mock_modbus_config_entry.add_to_hass(hass)
    result = await _async_start_flow(hass, TYPE_MODBUS)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MODBUS_USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured_device"


@pytest.mark.usefixtures("mock_modbus_connection_class", "mock_setup_entry")
async def test_modbus_and_cloud_entries_coexist(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test an inverter can be added over Modbus next to a cloud account."""
    mock_config_entry.add_to_hass(hass)
    result = await _async_start_flow(hass, TYPE_MODBUS)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MODBUS_USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MODBUS_SERIAL_NUMBER


@asynccontextmanager
async def _async_get_silent_unit(
    hass: HomeAssistant, params: ModbusTcpParams, unit_id: int
) -> AsyncIterator[MockModbusUnit]:
    """Give a unit of an inverter that does not reply."""
    unit = MockModbusConnection().for_unit(unit_id)
    unit.fail_requests(ModbusTimeoutError("no reply"))
    yield unit


@pytest.mark.usefixtures("mock_modbus_connection_class", "mock_setup_entry")
async def test_modbus_flow_no_reply(hass: HomeAssistant) -> None:
    """Test the Modbus flow shows an error when the inverter does not reply."""
    result = await _async_start_flow(hass, TYPE_MODBUS)
    with patch(
        "homeassistant.components.sunsynk.config_flow.async_get_temporary_unit",
        side_effect=_async_get_silent_unit,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MODBUS_USER_INPUT
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MODBUS_USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MODBUS_SERIAL_NUMBER


@pytest.mark.usefixtures("mock_modbus_connection_class", "mock_setup_entry")
async def test_modbus_flow_connection_in_use(hass: HomeAssistant) -> None:
    """Test the Modbus flow shows an error when the connection is not available."""
    result = await _async_start_flow(hass, TYPE_MODBUS)
    with patch(
        "homeassistant.components.sunsynk.config_flow.async_get_temporary_unit",
        side_effect=HomeAssistantError("in use"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MODBUS_USER_INPUT
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MODBUS_USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MODBUS_SERIAL_NUMBER


@pytest.mark.usefixtures("mock_modbus_connection_class", "mock_setup_entry")
async def test_modbus_flow_no_serial_number(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """Test the flow aborts when the inverter reports no serial number."""
    mock_modbus_unit.load_raw({"holding": dict.fromkeys(range(3, 8), 0)})
    result = await _async_start_flow(hass, TYPE_MODBUS)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MODBUS_USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_serial_number"
