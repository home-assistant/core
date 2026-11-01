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

PV_POWER = "sensor.s10_x_pv_power"
# The first register of each block a readings poll reads
READINGS_BLOCKS = (40068, 40096, 40088, 40105, 40137, 40188, 40200, 40202, 41000)


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
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
        UNIT_ID,
    )

    await hass.config_entries.async_unload(init_integration.entry_id)
    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_device_info(
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    init_integration: MockConfigEntry,
) -> None:
    """Test the power station lands in the device registry."""
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
    """Test an unreachable power station retries setup."""
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
    """Test a device switched to SunSpec mode fails setup for good."""
    seed(mock_unit, {40001: 0x5375})
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert (
        mock_config_entry.reason
        == "The device is not an E3/DC power station in E3/DC protocol mode"
    )


async def test_setup_fails_when_the_link_is_held_with_other_settings(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a shared link held with other settings fails setup for good."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.e3dc.async_get_unit",
        side_effect=HomeAssistantError("in use with baudrate 9600"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.error_reason_translation_key == "link_settings_in_use"


async def test_setup_fails_for_another_power_station(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
    mock_unit: MockModbusUnit,
) -> None:
    """Test setup refuses a power station with another serial number."""
    seed_identity(mock_unit, serial="S10-99999999999")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.error_reason_translation_key == "serial_mismatch"


async def test_refused_power_block_goes_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_unit: MockModbusUnit,
) -> None:
    """Test the sensors go unavailable while their block is refused."""
    mock_unit.fail_read(register(40068), IllegalDataAddressError())
    await _poll(hass, freezer)

    # Other blocks still answered, so the poll as a whole succeeded
    assert init_integration.runtime_data.last_update_success
    assert hass.states.get(PV_POWER).state == STATE_UNAVAILABLE

    mock_unit.fail_read(register(40068), None)
    await _poll(hass, freezer)

    assert hass.states.get(PV_POWER).state == "5321"


async def test_dead_link_makes_everything_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_unit: MockModbusUnit,
) -> None:
    """Test a dropped link marks the power station unavailable until it answers."""
    mock_unit.fail_requests(ModbusConnectionError())
    await _poll(hass, freezer)

    assert hass.states.get(PV_POWER).state == STATE_UNAVAILABLE

    mock_unit.fail_requests(None)
    await _poll(hass, freezer)

    assert hass.states.get(PV_POWER).state == "5321"


async def test_every_component_failing_marks_the_poll_failed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_unit: MockModbusUnit,
) -> None:
    """Test a poll where no component answers fails as a whole."""
    for index in READINGS_BLOCKS:
        mock_unit.fail_read(register(index), IllegalDataAddressError())
    await _poll(hass, freezer)

    assert not init_integration.runtime_data.last_update_success
    assert hass.states.get(PV_POWER).state == STATE_UNAVAILABLE

    for index in READINGS_BLOCKS:
        mock_unit.fail_read(register(index), None)
    await _poll(hass, freezer)

    assert hass.states.get(PV_POWER).state == "5321"
