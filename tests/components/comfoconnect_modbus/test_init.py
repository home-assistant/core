"""Tests for the Zehnder ComfoConnect PRO integration setup."""

from collections.abc import Generator
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
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.comfoconnect_modbus.const import (
    CONF_UNIT_ID,
    DOMAIN,
    SCAN_INTERVAL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from . import INPUT, MOCK_SERIAL_ENTRY_DATA, seed, seed_gateway

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
    """Test that the entry sets up and unloads."""
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
    """Test that a serial entry connects with its serial settings."""
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
    """Test that the gateway gets added to the device registry."""
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
    """Test that setup retries when the gateway is unreachable."""
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
    """Test that setup retries when the gateway has no ventilation unit."""
    seed(mock_unit, input_registers={0x0001: 50})  # Connection state
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
    """Test that only the entities of a failed read go unavailable."""
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
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that entities go unavailable while the link is down."""
    mock_unit.fail_requests(ModbusConnectionError("socket closed"))
    await _tick(hass, freezer)

    assert hass.states.get(AIRFLOW).state == STATE_UNAVAILABLE
    assert "Lost the Modbus link to the ComfoConnect PRO" in caplog.text

    mock_unit.fail_requests(None)
    await _tick(hass, freezer)

    assert hass.states.get(AIRFLOW).state == "175"


async def test_every_component_failing_marks_the_poll_failed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_unit: MockModbusUnit,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the poll fails when every read fails."""
    error = IllegalDataAddressError()
    # The first registers of the status, sensor and settings blocks
    mock_unit.fail_read(address(0x0001), error, register_type="input")
    mock_unit.fail_read(address(0x0007), error, register_type="input")
    mock_unit.fail_read(address(0x0001), error, register_type="holding")
    await _tick(hass, freezer)

    assert hass.states.get(AIRFLOW).state == STATE_UNAVAILABLE
    assert "The ComfoConnect PRO refused every read" in caplog.text


async def test_lost_ventilation_unit_makes_everything_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_unit: MockModbusUnit,
) -> None:
    """Test that entities go unavailable while the ventilation unit is lost."""
    seed(mock_unit, input_registers={0x0001: 7})  # Connection state
    await _tick(hass, freezer)

    assert hass.states.get(AIRFLOW).state == STATE_UNAVAILABLE

    seed(mock_unit, input_registers=INPUT)
    await _tick(hass, freezer)

    assert hass.states.get(AIRFLOW).state == "175"


async def test_setup_fails_when_the_link_is_held_with_other_settings(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that setup fails when the link is in use with other settings."""
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
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the poll reports no path when the gateway refuses every read."""
    # The first registers of the status, sensor and settings blocks
    mock_unit.fail_read(address(0x0001), error(), register_type="discrete")
    mock_unit.fail_read(address(0x0007), error(), register_type="input")
    mock_unit.fail_read(address(0x0001), error(), register_type="holding")
    await _tick(hass, freezer)

    assert hass.states.get(AIRFLOW).state == STATE_UNAVAILABLE
    assert "The ComfoConnect PRO has no path to the ventilation unit" in caplog.text


@pytest.fixture
def bus() -> MockModbusConnection:
    """One RS-485 bus with gateways on unit IDs 1 and 2."""
    connection = MockModbusConnection()
    seed_gateway(connection.for_unit(1))
    seed_gateway(connection.for_unit(2))
    return connection


@pytest.fixture
def connection_class(bus: MockModbusConnection) -> Generator[MagicMock]:
    """Patch `ModbusConnection` in core's modbus helper to return ``bus``."""
    with patch(
        "homeassistant.components.modbus.connection.ModbusConnection",
        return_value=bus,
    ) as connection_class:
        yield connection_class


async def test_two_gateways_share_one_serial_connection(
    hass: HomeAssistant, connection_class: MagicMock
) -> None:
    """Test that two gateways on one serial port share a connection."""
    first = MockConfigEntry(domain=DOMAIN, data=MOCK_SERIAL_ENTRY_DATA)
    second = MockConfigEntry(
        domain=DOMAIN, data={**MOCK_SERIAL_ENTRY_DATA, CONF_UNIT_ID: 2}
    )
    for entry in (first, second):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert first.state is ConfigEntryState.LOADED
    assert second.state is ConfigEntryState.LOADED
    connection_class.assert_called_once()
