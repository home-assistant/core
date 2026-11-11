"""Tests for the Zehnder ComfoConnect PRO integration setup."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from comfoconnect_pro_modbus.model import address
from freezegun.api import FrozenDateTimeFactory
from modbus_connection import (
    GatewayPathUnavailableError,
    GatewayTargetError,
    IllegalDataAddressError,
    ModbusConnectionError,
    ModbusSerialParams,
    ModbusTcpParams,
)
from modbus_connection.mock import MockModbusUnit
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.comfoconnect_modbus.const import DOMAIN, SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import INPUT, MOCK_SERIAL_ENTRY_DATA, seed

_SCAN = timedelta(seconds=SCAN_INTERVAL)
AIRFLOW = "sensor.comfoair_airflow"


async def _tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Run the next poll."""
    freezer.tick(_SCAN)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_setup_and_unload(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_get_unit: MagicMock,
) -> None:
    """Test the entry sets up over a unit from modbus and unloads."""
    assert init_integration.state is ConfigEntryState.LOADED
    mock_get_unit.assert_called_once_with(
        hass,
        init_integration,
        ModbusTcpParams(host="192.168.1.100", port=502),
        1,
    )

    await hass.config_entries.async_unload(init_integration.entry_id)
    assert init_integration.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize("platforms", [[]])
async def test_setup_over_serial(
    hass: HomeAssistant,
    mock_get_unit: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test a serial entry asks for the line settings it stored."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_SERIAL_ENTRY_DATA)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.LOADED
    mock_get_unit.assert_called_once_with(
        hass,
        entry,
        ModbusSerialParams(
            device="/dev/ttyUSB0", baudrate=19200, parity="E", stopbits=1
        ),
        1,
    )


async def test_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    init_integration: MockConfigEntry,
) -> None:
    """Test the gateway lands in the device registry."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, init_integration.entry_id), init_integration.entry_id
    )
    assert device == snapshot


@pytest.mark.usefixtures("mock_get_unit")
async def test_setup_retries_when_unreachable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_unit: MockModbusUnit,
) -> None:
    """Test an unreachable gateway retries setup."""
    mock_unit.fail_requests(ModbusConnectionError())
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_get_unit")
async def test_setup_retries_without_ventilation_unit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_unit: MockModbusUnit,
) -> None:
    """Test a gateway that lost its ventilation unit retries setup."""
    seed(mock_unit, input_registers={0x0001: 50})  # connection state
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.reason == (
        "The ComfoConnect PRO does not reach a supported ventilation unit "
        "(connection state 50)"
    )


async def test_failed_component_goes_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_unit: MockModbusUnit,
) -> None:
    """Test only the entities of a refused block go unavailable."""
    # Airflow, the first register of the sensor block
    mock_unit.fail_read(
        address(0x0007), IllegalDataAddressError(), register_type="input"
    )
    await _tick(hass, freezer)

    assert hass.states.get(AIRFLOW).state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.comfoair_active_error_1").state == (
        "filter_warning_flag"
    )

    mock_unit.fail_read(address(0x0007), None, register_type="input")
    await _tick(hass, freezer)

    assert hass.states.get(AIRFLOW).state == "175"


async def test_dead_link_makes_everything_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_unit: MockModbusUnit,
) -> None:
    """Test a dropped link marks the gateway unavailable until it answers."""
    mock_unit.fail_requests(ModbusConnectionError())
    await _tick(hass, freezer)

    assert hass.states.get(AIRFLOW).state == STATE_UNAVAILABLE

    mock_unit.fail_requests(None)
    await _tick(hass, freezer)

    assert hass.states.get(AIRFLOW).state == "175"


async def test_every_component_failing_marks_the_poll_failed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_unit: MockModbusUnit,
) -> None:
    """Test a poll where no component answers fails as a whole."""
    error = IllegalDataAddressError()
    # The first registers of the status, sensor and settings blocks
    mock_unit.fail_read(address(0x0001), error, register_type="input")
    mock_unit.fail_read(address(0x0007), error, register_type="input")
    mock_unit.fail_read(address(0x0001), error, register_type="holding")
    await _tick(hass, freezer)

    assert not init_integration.runtime_data.last_update_success
    assert hass.states.get(AIRFLOW).state == STATE_UNAVAILABLE


async def test_lost_ventilation_unit_makes_everything_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_unit: MockModbusUnit,
) -> None:
    """Test a gateway that loses its ventilation unit marks it unavailable."""
    seed(mock_unit, input_registers={0x0001: 7})  # connection state
    await _tick(hass, freezer)

    assert hass.states.get(AIRFLOW).state == STATE_UNAVAILABLE

    seed(mock_unit, input_registers=INPUT)
    await _tick(hass, freezer)

    assert hass.states.get(AIRFLOW).state == "175"


async def test_setup_fails_when_the_link_is_held_with_other_settings(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup fails with the modbus error when the link is in use with other settings."""
    mock_config_entry.add_to_hass(hass)
    placeholders = {
        "endpoint": "192.168.1.100:502",
        "existing_params": "port 503",
        "params": "port 502",
    }
    with patch(
        "homeassistant.components.comfoconnect_modbus.async_get_unit",
        side_effect=HomeAssistantError(
            translation_domain="modbus",
            translation_key="device_in_use",
            translation_placeholders=placeholders,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.error_reason_translation_domain == "modbus"
    assert mock_config_entry.error_reason_translation_key == "device_in_use"
    assert mock_config_entry.error_reason_translation_placeholders == placeholders


@pytest.mark.parametrize("error", [GatewayPathUnavailableError, GatewayTargetError])
async def test_gateway_refusing_every_read_reports_no_path(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_unit: MockModbusUnit,
    error: type[Exception],
) -> None:
    """Test a gateway that lost its unit and refuses every read says so."""
    # The first registers of the status, sensor and settings blocks
    mock_unit.fail_read(address(0x0001), error(), register_type="discrete")
    mock_unit.fail_read(address(0x0007), error(), register_type="input")
    mock_unit.fail_read(address(0x0001), error(), register_type="holding")
    await _tick(hass, freezer)

    coordinator = init_integration.runtime_data
    assert not coordinator.last_update_success
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert coordinator.last_exception.translation_key == "no_path_to_unit"
    assert hass.states.get(AIRFLOW).state == STATE_UNAVAILABLE


async def test_dead_link_keeps_the_modbus_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_unit: MockModbusUnit,
) -> None:
    """Test a lost link chains the Modbus error to the failure."""
    mock_unit.fail_requests(ModbusConnectionError("socket closed"))
    await _tick(hass, freezer)

    exception = init_integration.runtime_data.last_exception
    assert isinstance(exception, UpdateFailed)
    assert exception.translation_key == "modbus_error"
    assert isinstance(exception.__cause__, ModbusConnectionError)
