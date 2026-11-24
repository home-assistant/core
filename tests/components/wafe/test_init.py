"""Tests for the WAFE integration setup and unload."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import (
    IllegalDataAddressError,
    ModbusConnectionError,
    ModbusTcpParams,
    ModbusTimeoutError,
)
from modbus_connection.mock import MockModbusUnit
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.wafe.const import DOMAIN
from homeassistant.components.wafe.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import MOCK_HOST, MOCK_UNIT_ID

SENSOR_ENTITY = "sensor.wafe_w201_outdoor_temperature"


async def test_setup_and_unload(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_get_unit: MagicMock,
) -> None:
    """Test the entry sets up on a shared unit and unloads."""
    assert init_integration.state is ConfigEntryState.LOADED
    assert mock_get_unit.call_args.args[2:] == (
        ModbusTcpParams(host=MOCK_HOST, port=502),
        1,
    )

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_device_info(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the unit is registered as a device."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_UNIT_ID), init_integration.entry_id
    )
    assert device == snapshot


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ModbusTimeoutError(), id="timeout"),
        pytest.param(ModbusConnectionError(), id="connection"),
    ],
)
@pytest.mark.usefixtures("mock_get_unit")
async def test_setup_retries_when_unreachable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_unit: MockModbusUnit,
    error: Exception,
) -> None:
    """Test setup is retried while the unit does not answer."""
    mock_unit.fail_requests(error)
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_get_unit")
async def test_setup_retries_when_readings_are_refused(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_unit: MockModbusUnit,
) -> None:
    """Test setup is retried when the unit refuses its readings."""
    mock_unit.fail_read(1002, IllegalDataAddressError(), register_type="input")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_get_unit")
async def test_setup_fails_for_another_unit(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_unit: MockModbusUnit
) -> None:
    """Test setup fails when a different unit answers at the configured address."""
    mock_unit.input[1000] = 2000
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.error_reason_translation_key == "wrong_unit"


@pytest.mark.usefixtures("mock_get_unit")
async def test_setup_retries_when_identity_is_refused(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_unit: MockModbusUnit,
) -> None:
    """Test setup is retried when the unit refuses its identity."""
    mock_unit.fail_read(1000, IllegalDataAddressError(), register_type="input")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unit_goes_unavailable_and_recovers(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_unit: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities go unavailable while the unit is silent."""
    mock_unit.fail_requests(ModbusTimeoutError())
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(SENSOR_ENTITY).state == STATE_UNAVAILABLE

    mock_unit.fail_requests(None)
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(SENSOR_ENTITY).state == "2.2"
