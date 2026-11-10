"""Tests for the Intesis Modbus config flow."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, _patch, patch

from modbus_connection import (
    IllegalDataAddressError,
    ModbusSerialParams,
    ModbusTimeoutError,
    ServerDeviceBusyError,
)
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest
from pytest_homeassistant.common import MockConfigEntry, get_schema_suggested_value

from homeassistant.components.intesis_modbus.const import (
    CONF_HAS_VANE,
    CONF_TEMPERATURE_FORMAT,
    CONF_UNIT_ID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError

from . import (
    MOCK_ENTRY_DATA,
    MOCK_USER_INPUT,
    seed_initialising_single_unit,
    seed_single_unit,
)

TARGET = "homeassistant.components.intesis_modbus.config_flow.async_get_temporary_unit"


def _patch_temporary_unit(connection: MockModbusConnection) -> _patch:
    """Stand in for async_get_temporary_unit, handing out a unit on connection."""

    @asynccontextmanager
    async def _get_temporary_unit(
        hass: HomeAssistant, params: ModbusSerialParams, unit_id: int
    ) -> AsyncIterator[MockModbusUnit]:
        assert params == ModbusSerialParams(
            device="/dev/ttyUSB0", baudrate=9600, bytesize=8, parity="N", stopbits=2
        )
        yield connection.for_unit(unit_id)

    return patch(TARGET, side_effect=_get_temporary_unit)


class _RaisingTemporaryUnit:
    """Stand in for a temporary-unit context whose __aenter__ raises."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def __aenter__(self) -> None:
        raise self._error

    async def __aexit__(self, *args: object) -> None:
        return None


def _seeded(
    seed: Callable[[MockModbusUnit], None] = seed_single_unit,
) -> MockModbusConnection:
    connection = MockModbusConnection()
    seed(connection.for_unit(1))
    return connection


async def _submit_link(hass: HomeAssistant) -> ConfigFlowResult:
    """Start a user flow and submit the serial link settings."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_USER_INPUT
    )


async def _finish_features(
    hass: HomeAssistant,
    result: ConfigFlowResult,
    *,
    expected_default: bool = True,
    has_vane: bool = True,
) -> ConfigFlowResult:
    """Confirm the features step, checking what the probe pre-filled."""
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "features"
    assert (
        get_schema_suggested_value(result["data_schema"].schema, CONF_HAS_VANE)
        is expected_default
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HAS_VANE: has_vane}
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_flow(hass: HomeAssistant) -> None:
    """A gateway that identifies itself only needs the vane confirmed."""
    with _patch_temporary_unit(_seeded()):
        result = await _submit_link(hass)
    result = await _finish_features(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "INMBSMHI001R000"
    assert result["data"] == MOCK_ENTRY_DATA


@pytest.mark.usefixtures("mock_setup_entry")
async def test_initialising_gateway_asks_temperature_format(
    hass: HomeAssistant,
) -> None:
    """With every register at the init value the format cannot be detected."""
    with _patch_temporary_unit(_seeded(seed_initialising_single_unit)):
        result = await _submit_link(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "temperature_format"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TEMPERATURE_FORMAT: "celsius"}
    )
    result = await _finish_features(hass, result, expected_default=False)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {**MOCK_ENTRY_DATA, CONF_TEMPERATURE_FORMAT: "celsius"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_vane_at_init_value_defaults_to_no_vane(hass: HomeAssistant) -> None:
    """A unit that never reported a vane position is offered without one."""
    connection = _seeded()
    connection.for_unit(1).holding[3] = 0x8000
    with _patch_temporary_unit(connection):
        result = await _submit_link(hass)
    result = await _finish_features(
        hass, result, expected_default=False, has_vane=False
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {**MOCK_ENTRY_DATA, CONF_HAS_VANE: False}


@pytest.mark.parametrize(
    ("device_id", "brand"),
    [
        pytest.param(0x0801, "Daikin", id="daikin"),
        pytest.param(0x1500, "Panasonic", id="panasonic"),
        pytest.param(0x1F00, "Toshiba", id="toshiba"),
        pytest.param(0x1000, "LG", id="lg"),
        pytest.param(0x1400, "Hitachi", id="hitachi"),
        pytest.param(0x1200, "Samsung", id="samsung"),
    ],
)
async def test_untabled_brand_aborts(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, device_id: int, brand: str
) -> None:
    """A gateway of a brand without code tables is refused by name."""
    connection = _seeded()
    connection.for_unit(1).holding[49] = device_id
    with _patch_temporary_unit(connection):
        result = await _submit_link(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_brand"
    assert result["description_placeholders"] == {"brand": brand}
    assert mock_setup_entry.call_count == 0


async def test_unknown_device_id_aborts(hass: HomeAssistant) -> None:
    """A device that answers with an unknown device id is refused."""
    connection = _seeded()
    connection.for_unit(1).holding[49] = 0x7777
    with _patch_temporary_unit(connection):
        result = await _submit_link(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_device"


async def test_refused_device_id_register_aborts(hass: HomeAssistant) -> None:
    """A device that refuses the device id register is refused."""
    connection = _seeded()
    connection.for_unit(1).fail_read(49, IllegalDataAddressError())
    with _patch_temporary_unit(connection):
        result = await _submit_link(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_device"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_busy_gateway_can_be_retried(hass: HomeAssistant) -> None:
    """A gateway that answers busy is a connection error, not another device."""
    connection = _seeded()
    connection.for_unit(1).fail_read(49, ServerDeviceBusyError())
    with _patch_temporary_unit(connection):
        result = await _submit_link(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}
        connection.for_unit(1).fail_read(49, None)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )
    result = await _finish_features(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == MOCK_ENTRY_DATA


@pytest.mark.usefixtures("mock_setup_entry")
async def test_cannot_connect(hass: HomeAssistant) -> None:
    """A silent gateway shows cannot_connect and the flow can be retried."""
    connection = _seeded()
    connection.for_unit(1).fail_requests(ModbusTimeoutError())
    with _patch_temporary_unit(connection):
        result = await _submit_link(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}
        connection.for_unit(1).fail_requests(None)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )
    result = await _finish_features(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == MOCK_ENTRY_DATA


@pytest.mark.usefixtures("mock_setup_entry")
async def test_serial_port_in_use_with_other_settings(hass: HomeAssistant) -> None:
    """A port held by another entry with other link settings cannot be probed."""
    with patch(
        TARGET, return_value=_RaisingTemporaryUnit(HomeAssistantError("in use"))
    ):
        result = await _submit_link(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "device_in_use"}
    with _patch_temporary_unit(_seeded()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )
    result = await _finish_features(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == MOCK_ENTRY_DATA


async def test_duplicate_aborts(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The same port and unit id cannot be set up twice."""
    mock_config_entry.add_to_hass(hass)
    with _patch_temporary_unit(_seeded()):
        result = await _submit_link(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_overlapping_flows_create_one_entry(hass: HomeAssistant) -> None:
    """Two flows for the same gateway that both pass the probe end in one entry."""
    with _patch_temporary_unit(_seeded()):
        first = await _submit_link(hass)
        second = await _submit_link(hass)
    first = await _finish_features(hass, first)
    assert first["type"] is FlowResultType.CREATE_ENTRY
    second = await _finish_features(hass, second)
    assert second["type"] is FlowResultType.ABORT
    assert second["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("mock_setup_entry")
async def test_second_gateway_on_same_port(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Another unit id on a port that is already set up is a new entry."""
    mock_config_entry.add_to_hass(hass)
    connection = MockModbusConnection()
    seed_single_unit(connection.for_unit(2))
    with _patch_temporary_unit(connection):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**MOCK_USER_INPUT, CONF_UNIT_ID: 2}
        )
    result = await _finish_features(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {**MOCK_ENTRY_DATA, CONF_UNIT_ID: 2}
