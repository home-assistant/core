"""Test the De Dietrich config flow."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, _patch, patch

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
from homeassistant.const import CONF_HOST
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


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("system", "outdoor_register", "other_layout_register"),
    [
        pytest.param(SYSTEM_DIEMATIC_3, 7, 601, id="diematic_3"),
        pytest.param(SYSTEM_DIEMATIC_4, 7, 601, id="diematic_4"),
        pytest.param(SYSTEM_ISYSTEM, 601, 7, id="isystem"),
    ],
)
@pytest.mark.parametrize(
    "boiler_type",
    [pytest.param(24, id="known_type"), pytest.param(999, id="unknown_type")],
)
async def test_user_step_success(
    hass: HomeAssistant,
    system: str,
    outdoor_register: int,
    other_layout_register: int,
    boiler_type: int,
) -> None:
    """Test the flow reads the selected layout and stores the connection settings."""
    mock_conn = MockModbusConnection()
    unit = mock_conn.for_unit(10)
    seed_boiler(unit, boiler_type)
    user_input = {**MOCK_USER_INPUT, CONF_SYSTEM: system}

    with _patch_temporary_unit(mock_conn):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=user_input,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "De Dietrich"
    assert result["data"] == user_input
    assert any(
        event.register_type == "holding"
        and event.address <= outdoor_register < event.address + event.count
        for event in unit.read_events
    )
    assert not any(
        event.address <= other_layout_register < event.address + event.count
        for event in unit.read_events
    )


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


async def test_user_step_sensors_read_fails(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test cannot_connect when the sensors block fails though identity succeeds."""
    mock_conn = MockModbusConnection()
    unit = mock_conn.for_unit(10)
    seed_boiler(unit)
    unit.fail_read(601, ModbusTimeoutError("no sensors"))

    with _patch_temporary_unit(mock_conn):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.parametrize(
    ("host", "system"),
    [
        pytest.param("boiler.local", SYSTEM_ISYSTEM, id="same_connection"),
        pytest.param("BOILER.LOCAL", SYSTEM_ISYSTEM, id="host_case"),
        pytest.param("boiler.local", SYSTEM_DIEMATIC_3, id="different_system"),
    ],
)
async def test_user_step_already_configured(
    hass: HomeAssistant, host: str, system: str
) -> None:
    """Test duplicates are rejected without connecting to the boiler."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={**MOCK_USER_INPUT, CONF_HOST: "boiler.local"}
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.dedietrich.config_flow.async_get_temporary_unit",
        side_effect=ModbusConnectionError("offline"),
    ) as mock_get_unit:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={**MOCK_USER_INPUT, CONF_HOST: host, CONF_SYSTEM: system},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_get_unit.assert_not_called()


async def test_user_step_duplicate_added_during_probe(hass: HomeAssistant) -> None:
    """Test an entry added during the probe is rejected by the final check."""
    mock_conn = MockModbusConnection()
    seed_boiler(mock_conn.for_unit(10))

    @asynccontextmanager
    async def _get_temporary_unit(
        hass: HomeAssistant, params: ModbusTcpParams, unit_id: int
    ) -> AsyncIterator[MockModbusUnit]:
        MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT).add_to_hass(hass)
        yield mock_conn.for_unit(unit_id)

    with patch(
        "homeassistant.components.dedietrich.config_flow.async_get_temporary_unit",
        side_effect=_get_temporary_unit,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
