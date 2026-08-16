"""Test the Sofar Inverter Modbus config flow."""

from collections.abc import Callable
from unittest.mock import AsyncMock, patch

from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest

from homeassistant import config_entries
from homeassistant.components.sofar_modbus.const import DEFAULT_NAME, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_MODEL, MOCK_SERIAL, MOCK_USER_INPUT, seed_pv_inverter

from tests.common import MockConfigEntry

# A recognized prefix with no model in sofar-modbus's own table.
_UNMODELED_SERIAL = "SA1XXES100XX"


async def test_user_step_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test successful user flow creating a config entry."""
    mock_conn = MockModbusConnection()
    seed_pv_inverter(mock_conn.for_unit(1))

    with patch(
        "homeassistant.components.sofar_modbus.config_flow.ModbusConnection",
        return_value=mock_conn,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_MODEL
    assert result["data"] == MOCK_USER_INPUT
    assert result["result"].unique_id == MOCK_SERIAL
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_step_success_without_model(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test successful flow falls back to the default title when the model is unknown."""
    mock_conn = MockModbusConnection()
    seed_pv_inverter(mock_conn.for_unit(1), serial=_UNMODELED_SERIAL)

    with patch(
        "homeassistant.components.sofar_modbus.config_flow.ModbusConnection",
        return_value=mock_conn,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == MOCK_USER_INPUT
    assert result["result"].unique_id == _UNMODELED_SERIAL


def _seed_unreachable(unit: MockModbusUnit) -> None:
    unit.fail_requests(ModbusTimeoutError("stuck"))


def _seed_unrecognized(unit: MockModbusUnit) -> None:
    pass  # unseeded registers decode to an empty, unrecognized serial


@pytest.mark.parametrize(
    ("seed", "expected_error"),
    [
        pytest.param(_seed_unreachable, "cannot_connect", id="cannot_connect"),
        pytest.param(
            _seed_unrecognized, "unrecognized_inverter", id="unrecognized_inverter"
        ),
    ],
)
async def test_user_step_errors(
    hass: HomeAssistant,
    seed: Callable[[MockModbusUnit], None],
    expected_error: str,
) -> None:
    """Test the user step reports the right error for each probe failure."""
    mock_conn = MockModbusConnection()
    seed(mock_conn.for_unit(1))

    with patch(
        "homeassistant.components.sofar_modbus.config_flow.ModbusConnection",
        return_value=mock_conn,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}


async def test_user_step_cannot_connect_then_recovers(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the user step can be resubmitted successfully after a connection failure."""
    unreachable_conn = MockModbusConnection()
    unreachable_conn.for_unit(1).fail_requests(ModbusTimeoutError("stuck"))

    with patch(
        "homeassistant.components.sofar_modbus.config_flow.ModbusConnection",
        return_value=unreachable_conn,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["errors"] == {"base": "cannot_connect"}

    working_conn = MockModbusConnection()
    seed_pv_inverter(working_conn.for_unit(1))

    with patch(
        "homeassistant.components.sofar_modbus.config_flow.ModbusConnection",
        return_value=working_conn,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY


async def test_user_step_already_configured(hass: HomeAssistant) -> None:
    """Test aborting when the inverter is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=MOCK_SERIAL, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)

    mock_conn = MockModbusConnection()
    seed_pv_inverter(mock_conn.for_unit(1))

    with patch(
        "homeassistant.components.sofar_modbus.config_flow.ModbusConnection",
        return_value=mock_conn,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
