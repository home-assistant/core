"""Test the De Dietrich config flow."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, _patch, patch

from diematic_modbus import Diematic, DiematicISystem, DiematicVariant
from modbus_connection import ModbusConnectionError, ModbusTcpParams, ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest

from homeassistant import config_entries
from homeassistant.components.dedietrich.const import (
    CONF_SYSTEM,
    DOMAIN,
    SYSTEM_DIEMATIC_3,
    SYSTEM_DIEMATIC_4,
    SYSTEM_ISYSTEM,
)
from homeassistant.components.dedietrich.device import build_device
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_USER_INPUT, seed_boiler

from tests.common import MockConfigEntry


def _patch_temporary_unit(connection: MockModbusConnection) -> _patch:
    """Stand in for async_get_temporary_unit, handing out a unit on connection."""

    @asynccontextmanager
    async def _get_temporary_unit(
        hass: HomeAssistant, params: ModbusTcpParams, unit_id: int
    ) -> AsyncIterator[MockModbusUnit]:
        yield connection.for_unit(unit_id)

    return patch(
        "homeassistant.components.dedietrich.config_flow.async_get_temporary_unit",
        side_effect=_get_temporary_unit,
    )


async def test_user_step_shows_form(hass: HomeAssistant) -> None:
    """Test the initial form renders with no errors before any input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def _run_user_flow(
    hass: HomeAssistant, system: str
) -> tuple[config_entries.ConfigFlowResult, list[Diematic | DiematicISystem]]:
    """Drive the user step for one system and capture the built device."""
    mock_conn = MockModbusConnection()
    seed_boiler(mock_conn.for_unit(10))
    built: list[Diematic | DiematicISystem] = []

    def _capture(unit: object, system_arg: str) -> Diematic | DiematicISystem:
        device = build_device(unit, system_arg)
        built.append(device)
        return device

    with (
        _patch_temporary_unit(mock_conn),
        patch(
            "homeassistant.components.dedietrich.config_flow.build_device",
            side_effect=_capture,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={**MOCK_USER_INPUT, CONF_SYSTEM: system},
        )
    return result, built


@pytest.mark.parametrize(
    ("system", "expected_variant"),
    [
        pytest.param(SYSTEM_DIEMATIC_3, DiematicVariant.DIEMATIC_3, id="diematic_3"),
        pytest.param(SYSTEM_DIEMATIC_4, DiematicVariant.DIEMATIC_4, id="diematic_4"),
    ],
)
async def test_user_step_base_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    system: str,
    expected_variant: DiematicVariant,
) -> None:
    """Test a base-layout flow builds a Diematic with the chosen variant."""
    result, built = await _run_user_flow(hass, system)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SYSTEM] == system
    assert len(built) == 1
    assert isinstance(built[0], Diematic)
    assert built[0].variant is expected_variant


async def test_user_step_isystem_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test an iSystem flow builds a DiematicISystem."""
    result, built = await _run_user_flow(hass, SYSTEM_ISYSTEM)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SYSTEM] == SYSTEM_ISYSTEM
    assert len(built) == 1
    assert isinstance(built[0], DiematicISystem)


async def test_user_step_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the user step reports cannot_connect on a dead link, then recovers."""
    mock_conn = MockModbusConnection()
    mock_conn.for_unit(10).fail_requests(ModbusConnectionError("stuck"))

    with _patch_temporary_unit(mock_conn):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["description_placeholders"] == {"error": "stuck"}

    working_conn = MockModbusConnection()
    seed_boiler(working_conn.for_unit(10))

    with _patch_temporary_unit(working_conn):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_step_identity_read_fails(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test cannot_connect when the identity read fails though the link is alive."""
    mock_conn = MockModbusConnection()
    mock_conn.for_unit(10).fail_read(457, ModbusTimeoutError("no identity"))

    with _patch_temporary_unit(mock_conn):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_step_already_configured(hass: HomeAssistant) -> None:
    """Test aborting when the same boiler connection is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)

    mock_conn = MockModbusConnection()
    seed_boiler(mock_conn.for_unit(10))

    with _patch_temporary_unit(mock_conn):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
