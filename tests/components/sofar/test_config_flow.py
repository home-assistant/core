"""Test the Sofar Inverter Modbus config flow."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, _patch, patch

from modbus_connection import ModbusTcpParams, ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest

from homeassistant import config_entries
from homeassistant.components.sofar.const import DEFAULT_NAME, DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError

from . import MOCK_MODEL, MOCK_SERIAL, MOCK_USER_INPUT, seed_pv_inverter

from tests.common import MockConfigEntry, get_schema_suggested_value

# A recognized prefix with no model in sofar-modbus's own table.
_UNMODELED_SERIAL = "SA1XXES100XX"


def _patch_temporary_unit(connection: MockModbusConnection) -> _patch:
    """Stand in for async_get_temporary_unit, handing out a unit on connection."""

    @asynccontextmanager
    async def _get_temporary_unit(
        hass: HomeAssistant, params: ModbusTcpParams, unit_id: int
    ) -> AsyncIterator[MockModbusUnit]:
        yield connection.for_unit(unit_id)

    return patch(
        "homeassistant.components.sofar.config_flow.async_get_temporary_unit",
        side_effect=_get_temporary_unit,
    )


class _RaisingTemporaryUnit:
    """Stand in for a temporary-unit context whose __aenter__ raises."""

    def __init__(self, error: Exception) -> None:
        """Initialize with the error to raise on entry."""
        self._error = error

    async def __aenter__(self) -> None:
        raise self._error

    async def __aexit__(self, *args: object) -> None:
        """No cleanup: entry never succeeded."""


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
    """Test successful user flow creating a config entry."""
    mock_conn = MockModbusConnection()
    seed_pv_inverter(mock_conn.for_unit(1))

    with _patch_temporary_unit(mock_conn):
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
    """Test the flow falls back to the default title for an unknown model."""
    mock_conn = MockModbusConnection()
    seed_pv_inverter(mock_conn.for_unit(1), serial=_UNMODELED_SERIAL)

    with _patch_temporary_unit(mock_conn):
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
    """No-op: unseeded registers already decode to an unrecognized serial."""


@pytest.mark.parametrize(
    ("seed", "expected_error", "expected_placeholders"),
    [
        pytest.param(
            _seed_unreachable,
            "cannot_connect",
            {"error": "stuck"},
            id="cannot_connect",
        ),
        pytest.param(
            _seed_unrecognized,
            "unrecognized_inverter",
            {},
            id="unrecognized_inverter",
        ),
    ],
)
async def test_user_step_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    seed: Callable[[MockModbusUnit], None],
    expected_error: str,
    expected_placeholders: dict[str, str],
) -> None:
    """Test the user step reports the right error and recovers, per failure."""
    mock_conn = MockModbusConnection()
    seed(mock_conn.for_unit(1))

    with _patch_temporary_unit(mock_conn):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}
    assert result["description_placeholders"] == expected_placeholders

    working_conn = MockModbusConnection()
    seed_pv_inverter(working_conn.for_unit(1))

    with _patch_temporary_unit(working_conn):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_step_link_settings_conflict(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test a shared-connection link-settings clash surfaces its own message."""
    error = HomeAssistantError(
        "Modbus device ('192.168.1.100', 502) is already in use with different "
        "link settings"
    )
    with patch(
        "homeassistant.components.sofar.config_flow.async_get_temporary_unit",
        return_value=_RaisingTemporaryUnit(error),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["description_placeholders"] == {"error": str(error)}


async def test_user_step_already_configured(hass: HomeAssistant) -> None:
    """Test aborting when the inverter is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=MOCK_SERIAL, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)

    mock_conn = MockModbusConnection()
    seed_pv_inverter(mock_conn.for_unit(1))

    with _patch_temporary_unit(mock_conn):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


_NEW_USER_INPUT = {**MOCK_USER_INPUT, CONF_HOST: "192.168.1.200"}


async def test_reconfigure_updates_the_entry(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test reconfigure updates the entry and reloads it."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=MOCK_SERIAL, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_conn = MockModbusConnection()
    seed_pv_inverter(mock_conn.for_unit(1))

    with _patch_temporary_unit(mock_conn):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _NEW_USER_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == _NEW_USER_INPUT


async def test_reconfigure_rejects_a_different_serial(hass: HomeAssistant) -> None:
    """Test reconfigure aborts if the inverter's serial doesn't match."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=MOCK_SERIAL, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)

    mock_conn = MockModbusConnection()
    seed_pv_inverter(mock_conn.for_unit(1), serial=_UNMODELED_SERIAL)

    with _patch_temporary_unit(mock_conn):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _NEW_USER_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert entry.data == MOCK_USER_INPUT


@pytest.mark.parametrize(
    ("seed", "expected_error", "expected_placeholders"),
    [
        pytest.param(
            _seed_unreachable,
            "cannot_connect",
            {"error": "stuck"},
            id="cannot_connect",
        ),
        pytest.param(
            _seed_unrecognized,
            "unrecognized_inverter",
            {},
            id="unrecognized_inverter",
        ),
    ],
)
async def test_reconfigure_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    seed: Callable[[MockModbusUnit], None],
    expected_error: str,
    expected_placeholders: dict[str, str],
) -> None:
    """Test the reconfigure step reports the right error and recovers."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=MOCK_SERIAL, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)

    mock_conn = MockModbusConnection()
    seed(mock_conn.for_unit(1))

    with _patch_temporary_unit(mock_conn):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _NEW_USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": expected_error}
    assert result["description_placeholders"] == expected_placeholders
    assert entry.data == MOCK_USER_INPUT
    # The retry starts from what was typed, not from the stored entry.
    assert (
        get_schema_suggested_value(result["data_schema"].schema, CONF_HOST)
        == _NEW_USER_INPUT[CONF_HOST]
    )

    working_conn = MockModbusConnection()
    seed_pv_inverter(working_conn.for_unit(1))

    with _patch_temporary_unit(working_conn):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _NEW_USER_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == _NEW_USER_INPUT
