"""Tests for the E3/DC config flow."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, _patch, patch

from modbus_connection import ModbusTcpParams, ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.e3dc.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError

from . import MOCK_ENTRY_DATA, MOCK_MODEL, MOCK_SERIAL, MOCK_TITLE, seed, seed_identity


def _patch_temporary_unit(connection: MockModbusConnection) -> _patch[AsyncMock]:
    """Stand in for async_get_temporary_unit, handing out a unit on connection."""

    @asynccontextmanager
    async def _get_temporary_unit(
        hass: HomeAssistant, params: ModbusTcpParams, unit_id: int
    ) -> AsyncIterator[MockModbusUnit]:
        yield connection.for_unit(unit_id)

    return patch(
        "homeassistant.components.e3dc.config_flow.async_get_temporary_unit",
        side_effect=_get_temporary_unit,
    )


@pytest.fixture
def identified() -> MockModbusConnection:
    """A connection to a power station that answers its identity."""
    connection = MockModbusConnection()
    seed_identity(connection.for_unit(1))
    return connection


@pytest.mark.parametrize(
    ("model", "title"),
    [
        pytest.param(MOCK_MODEL, MOCK_TITLE, id="model"),
        pytest.param("one", "E3/DC One", id="lower_case_model"),
        pytest.param("", "E3/DC", id="no_model"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_success(
    hass: HomeAssistant, identified: MockModbusConnection, model: str, title: str
) -> None:
    """Test the flow creates an entry named after the model, with the serial number as unique ID."""
    seed_identity(identified.for_unit(1), model=model)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with _patch_temporary_unit(identified) as mock_temporary_unit:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.168.1.100", CONF_PORT: 1502}
        )

    mock_temporary_unit.assert_called_once_with(
        hass, ModbusTcpParams(host="192.168.1.100", port=1502), 1
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == title
    assert result["data"] == {CONF_HOST: "192.168.1.100", CONF_PORT: 1502}
    assert result["result"].unique_id == MOCK_SERIAL


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        pytest.param(HomeAssistantError("in use"), "cannot_connect", id="in_use"),
        pytest.param(RuntimeError("bug"), "unknown", id="unexpected"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_cannot_connect(
    hass: HomeAssistant,
    identified: MockModbusConnection,
    error: Exception,
    expected: str,
) -> None:
    """Test the form shows an error when opening the connection fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(
        "homeassistant.components.e3dc.config_flow.async_get_temporary_unit",
        side_effect=error,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_ENTRY_DATA
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}

    with _patch_temporary_unit(identified):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_ENTRY_DATA
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_timeout(
    hass: HomeAssistant, identified: MockModbusConnection
) -> None:
    """Test the form shows an error when the power station does not answer."""
    identified.for_unit(1).fail_requests(ModbusTimeoutError())
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with _patch_temporary_unit(identified):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_ENTRY_DATA
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    identified.for_unit(1).fail_requests(None)
    with _patch_temporary_unit(identified):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_ENTRY_DATA
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("holding", "expected"),
    [
        # SunSpec mode replaces the E3/DC marker in register 40001 with "Su"
        pytest.param({40001: 0x5375}, "not_e3dc", id="sunspec_mode"),
        pytest.param({40001: 0xE3DC}, "no_serial_number", id="no_serial"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_wrong_device(
    hass: HomeAssistant, holding: dict[int, int | list[int]], expected: str
) -> None:
    """Test the form shows an error for a device in SunSpec mode or without a serial number."""
    connection = MockModbusConnection()
    seed(connection.for_unit(1), holding)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with _patch_temporary_unit(connection):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_ENTRY_DATA
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}

    seed_identity(connection.for_unit(1))
    with _patch_temporary_unit(connection):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_ENTRY_DATA
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_already_configured(
    hass: HomeAssistant,
    identified: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a power station that is already set up aborts the flow."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with _patch_temporary_unit(identified):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_ENTRY_DATA
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
