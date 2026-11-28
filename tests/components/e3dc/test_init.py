"""Tests for the E3/DC integration setup."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from e3dc_ess_modbus.model import register
from freezegun.api import FrozenDateTimeFactory
from modbus_connection import (
    IllegalDataAddressError,
    ModbusConnectionError,
    ModbusTcpParams,
)
from modbus_connection.mock import MockModbusUnit
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.e3dc.const import DOMAIN, SCAN_INTERVAL, UNIT_ID
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from . import MOCK_SERIAL, seed, seed_identity

PV_POWER = "sensor.e3_dc_s10_x_pv_power"


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_setup_and_unload(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_get_unit: MagicMock,
) -> None:
    """Test the entry connects through the modbus integration, sets up and unloads."""
    assert init_integration.state is ConfigEntryState.LOADED
    mock_get_unit.assert_called_once_with(
        hass,
        init_integration,
        ModbusTcpParams(host="192.168.1.100", port=502),
        UNIT_ID,
    )

    await hass.config_entries.async_unload(init_integration.entry_id)
    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_device_info(
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    init_integration: MockConfigEntry,
) -> None:
    """Test the power station is registered as a device with its identity."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL), init_integration.entry_id
    )
    assert device == snapshot


async def test_setup_retries_when_unreachable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
    mock_unit: MockModbusUnit,
) -> None:
    """Test setup is retried while the power station does not answer."""
    mock_unit.fail_requests(ModbusConnectionError())
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_fails_when_not_e3dc(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
    mock_unit: MockModbusUnit,
) -> None:
    """Test setup fails without retry after the power station is switched to SunSpec mode."""
    # SunSpec mode replaces the E3/DC marker in register 40001 with "Su"
    seed(mock_unit, {40001: 0x5375})
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert (
        mock_config_entry.reason
        == "The device is not an E3/DC power station in E3/DC protocol mode"
    )


async def test_setup_fails_when_connection_is_in_use(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup fails with the modbus error when another integration uses the address with other settings."""
    mock_config_entry.add_to_hass(hass)
    placeholders = {
        "endpoint": "192.168.1.100:502",
        "existing_params": "port 503",
        "params": "port 502",
    }
    with patch(
        "homeassistant.components.e3dc.async_get_unit",
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


async def test_setup_fails_for_a_different_power_station(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
    mock_unit: MockModbusUnit,
) -> None:
    """Test setup fails when a different power station answers at the configured address."""
    # The config flow stored the serial number of the station it found as the unique ID
    seed_identity(mock_unit, serial="S10-99999999999")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.error_reason_translation_key == "serial_mismatch"


async def test_refused_read_makes_sensors_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_unit: MockModbusUnit,
) -> None:
    """Test the sensors are unavailable while the power station refuses to read a value."""
    # Register 40068 holds the PV power
    mock_unit.fail_read(register(40068), IllegalDataAddressError())
    await _poll(hass, freezer)

    assert not init_integration.runtime_data.last_update_success
    assert hass.states.get(PV_POWER).state == STATE_UNAVAILABLE

    mock_unit.fail_read(register(40068), None)
    await _poll(hass, freezer)

    assert hass.states.get(PV_POWER).state == "5321"


async def test_lost_connection_makes_sensors_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_unit: MockModbusUnit,
) -> None:
    """Test the sensors are unavailable while the connection to the power station is down."""
    mock_unit.fail_requests(ModbusConnectionError())
    await _poll(hass, freezer)

    assert hass.states.get(PV_POWER).state == STATE_UNAVAILABLE

    mock_unit.fail_requests(None)
    await _poll(hass, freezer)

    assert hass.states.get(PV_POWER).state == "5321"
