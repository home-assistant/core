"""Test the KACO Modbus config flow."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, _patch, patch

from kaco_modbus.testing import BLUEPLANET_86TL3, with_manufacturer
from modbus_connection import ModbusTcpParams, ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest

from homeassistant.components.kaco_modbus.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError

from . import MOCK_MODEL, MOCK_SERIAL, MOCK_USER_INPUT

from tests.common import MockConfigEntry

TARGET = "homeassistant.components.kaco_modbus.config_flow.async_get_temporary_unit"


def _serving(image: dict[int, int]) -> _patch:
    """Patch the temporary unit onto a device answering with *image*."""
    connection = MockModbusConnection()
    connection.for_unit(1).load_raw({"holding": dict(image)})

    @asynccontextmanager
    async def _get_unit(
        hass: HomeAssistant, params: ModbusTcpParams, unit_id: int
    ) -> AsyncIterator[MockModbusUnit]:
        yield connection.for_unit(unit_id)

    return patch(TARGET, side_effect=_get_unit)


def _raising(error: Exception) -> _patch:
    """Patch the temporary unit so acquiring it fails."""
    return patch(TARGET, side_effect=error)


@pytest.mark.usefixtures("mock_temporary_unit")
async def test_user_step_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the form renders and a successful flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_MODEL
    assert result["data"] == MOCK_USER_INPUT
    # The serial survives an address change, which a host or port does not.
    assert result["result"].unique_id == MOCK_SERIAL
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("failure", "expected_error"),
    [
        # Another vendor's SunSpec inverter answers the same models at the
        # same addresses, so it has to be told apart by its manufacturer.
        (
            lambda: _serving(with_manufacturer(BLUEPLANET_86TL3, "Fronius")),
            "not_a_kaco_inverter",
        ),
        (
            lambda: _serving(dict.fromkeys(range(40000, 40010), 0)),
            "not_a_sunspec_inverter",
        ),
        (lambda: _raising(ModbusTimeoutError("no answer")), "cannot_connect"),
        # The device is already held on different link settings.
        (lambda: _raising(HomeAssistantError("in use")), "cannot_connect"),
        (lambda: _raising(RuntimeError("boom")), "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_temporary_unit")
async def test_user_step_errors_then_recovers(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    failure: Callable[[], _patch],
    expected_error: str,
) -> None:
    """Test each failure shows on the form, and the flow still completes."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with failure():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # The healthy device the fixture serves is back once the failure lifts.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MOCK_SERIAL


@pytest.mark.usefixtures("mock_temporary_unit")
async def test_user_step_aborts_when_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the same inverter cannot be added twice, even at a new address."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**MOCK_USER_INPUT, "host": "192.168.1.101"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
