"""Test the KACO Modbus config flow."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, _patch, patch

from kaco_modbus.testing import BLUEPLANET_86TL3, with_manufacturer
from modbus_connection import ModbusTcpParams, ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest

from homeassistant import config_entries
from homeassistant.components.kaco_modbus.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError

from . import MOCK_MODEL, MOCK_SERIAL, MOCK_USER_INPUT

from tests.common import MockConfigEntry


def _patch_temporary_unit(connection: MockModbusConnection) -> _patch:
    """Stand in for async_get_temporary_unit, handing out a unit on connection."""

    @asynccontextmanager
    async def _get_temporary_unit(
        hass: HomeAssistant, params: ModbusTcpParams, unit_id: int
    ) -> AsyncIterator[MockModbusUnit]:
        yield connection.for_unit(unit_id)

    return patch(
        "homeassistant.components.kaco_modbus.config_flow.async_get_temporary_unit",
        side_effect=_get_temporary_unit,
    )


def _connection_serving(image: dict[int, int]) -> MockModbusConnection:
    """A mock connection answering with *image*."""
    connection = MockModbusConnection()
    connection.for_unit(1).load_raw({"holding": dict(image)})
    return connection


async def test_user_step_shows_form(hass: HomeAssistant) -> None:
    """Test the initial form renders with no errors before any input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_user_step_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test a successful flow creates an entry keyed by serial number."""
    with _patch_temporary_unit(_connection_serving(BLUEPLANET_86TL3)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_MODEL
    assert result["data"] == MOCK_USER_INPUT
    # The serial survives an address change, which a host or port does not.
    assert result["result"].unique_id == MOCK_SERIAL
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_step_rejects_another_brand(hass: HomeAssistant) -> None:
    """Test a SunSpec inverter that is not a KACO is refused.

    Another vendor answers the same models at the same addresses, so without
    this it would be added and then read on KACO's terms.
    """
    foreign = _connection_serving(with_manufacturer(BLUEPLANET_86TL3, "Fronius"))

    with _patch_temporary_unit(foreign):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "not_a_kaco_inverter"}


async def test_user_step_rejects_a_non_sunspec_device(hass: HomeAssistant) -> None:
    """Test something answering Modbus but not SunSpec is refused."""
    silent = _connection_serving(dict.fromkeys(range(40000, 40010), 0))

    with _patch_temporary_unit(silent):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "not_a_sunspec_inverter"}


@pytest.mark.parametrize(
    "error",
    [
        ModbusTimeoutError("no answer"),
        HomeAssistantError("already in use with different link settings"),
    ],
)
async def test_user_step_cannot_connect(hass: HomeAssistant, error: Exception) -> None:
    """Test an unreachable address, and one held on different link settings."""
    connection = _connection_serving(BLUEPLANET_86TL3)
    connection.for_unit(1).fail_requests(error)

    with _patch_temporary_unit(connection):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_step_recovers_after_an_error(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the form can be resubmitted once the inverter answers."""
    connection = _connection_serving(BLUEPLANET_86TL3)
    connection.for_unit(1).fail_requests(ModbusTimeoutError("no answer"))

    with _patch_temporary_unit(connection):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )
        assert result["errors"] == {"base": "cannot_connect"}

        connection.for_unit(1).fail_requests(None)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MOCK_SERIAL


async def test_user_step_aborts_when_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the same inverter cannot be added twice, even at a new address."""
    mock_config_entry.add_to_hass(hass)

    with _patch_temporary_unit(_connection_serving(BLUEPLANET_86TL3)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={**MOCK_USER_INPUT, "host": "192.168.1.101"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
