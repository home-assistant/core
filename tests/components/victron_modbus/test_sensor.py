"""Test Victron Modbus sensors."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import IllegalDataAddressError, ModbusTimeoutError
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.victron_modbus.const import DOMAIN, READINGS_SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import SERIAL, VM_3P75CT, set_identity, set_readings


async def _next_poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let the next poll of both coordinators run."""
    freezer.tick(READINGS_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_total_sensor_follows_the_device(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_unit,
) -> None:
    """A total follows the device, and is unavailable while it can't be read."""
    mock_unit.holding[0x3034] = 0
    mock_unit.holding[0x3035] = 1200  # total_forward_energy: 12.00 kWh
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    unique_id = f"{SERIAL}_total_forward_energy"
    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "12.0"

    coordinator = mock_config_entry.runtime_data.readings

    # Any change is taken over, a decrease (such as a replaced meter) included.
    mock_unit.holding[0x3035] = 1190  # 11.90 kWh
    await _next_poll(hass, freezer)
    assert hass.states.get(entity_id).state == "11.9"

    # A reading the device reports as unavailable (sentinel value decoded as
    # None) has no value.
    mock_unit.holding[0x3034] = 0xFFFF
    mock_unit.holding[0x3035] = 0xFFFF
    await _next_poll(hass, freezer)
    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    # A device that stops answering makes the sensor unavailable.
    mock_unit.fail_requests(ModbusTimeoutError())
    await _next_poll(hass, freezer)
    assert not coordinator.last_update_success
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # It comes back with the device.
    mock_unit.fail_requests(None)
    mock_unit.holding[0x3034] = 0
    mock_unit.holding[0x3035] = 1250  # 12.50 kWh
    await _next_poll(hass, freezer)
    assert hass.states.get(entity_id).state == "12.5"


async def test_failed_sub_system_is_unavailable(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_unit,
) -> None:
    """When only the phases fail to read, only the phase measurements go unavailable."""
    mock_unit.holding[0x3040] = 23010  # phase_1 voltage: 230.10 V
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    def state(key: str) -> str:
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{SERIAL}_{key}"
        )
        return hass.states.get(entity_id).state

    assert state("phase_1_voltage") == "230.1"

    mock_unit.fail_read(0x3040, IllegalDataAddressError())
    await _next_poll(hass, freezer)

    assert state("phase_1_voltage") == STATE_UNAVAILABLE
    assert state("total_power") == "0"
    assert state("phase_1_forward_energy") == STATE_UNAVAILABLE

    mock_unit.fail_read(0x3040, None)
    await _next_poll(hass, freezer)

    assert state("phase_1_voltage") == "230.1"


async def test_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_unit,
) -> None:
    """The device is registered under its serial number."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, SERIAL), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.serial_number == SERIAL
    assert device.model == "VM-3P75CT"
    assert device.manufacturer == "Victron Energy"
    assert device.hw_version == "3"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("product_id", "model"),
    [(0xA1B1, "vm_3p75ct"), (0xA1B2, "vm_3p5a"), (0xC02F, "p1link")],
    ids=["vm_3p75ct", "vm_3p5a", "p1link"],
)
async def test_all_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_unit,
    product_id: int,
    model: str,
) -> None:
    """Every model's sensors, with their state and registry entries."""
    set_identity(mock_unit, product_id)
    set_readings(mock_unit)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"{model} ({SERIAL})",
        data={"host": "192.168.1.101", "model": model},
        unique_id=SERIAL,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_power_is_polled_apart(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_unit,
) -> None:
    """Power has its own poll, so it stays live when the rest can't be read."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    data = mock_config_entry.runtime_data
    assert data.power.update_interval == timedelta(seconds=1)
    assert data.readings.update_interval == timedelta(seconds=10)

    def state(key: str) -> str:
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{SERIAL}_{key}"
        )
        return hass.states.get(entity_id).state

    mock_unit.fail_read(0x3034, IllegalDataAddressError())
    mock_unit.fail_read(0x3040, IllegalDataAddressError())
    mock_unit.holding[0x3080] = [0, 750]  # total power: 750 W
    await _next_poll(hass, freezer)

    assert not data.readings.last_update_success
    assert state("phase_1_voltage") == STATE_UNAVAILABLE
    assert state("total_power") == "750"
    assert state("phase_1_power") == "0"


async def test_only_reported_readings_get_a_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_unit,
) -> None:
    """Readings unavailable at setup get a sensor once the device reports them."""
    set_readings(mock_unit)
    mock_unit.holding[0x3048] = 0x7FFF  # L2 voltage: not available
    mock_unit.holding[0x100B] = 0xFFFF  # hardware version: not reported
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    unique_ids = {
        entry.unique_id.removeprefix(f"{SERIAL}_")
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    }
    assert "phase_2_voltage" not in unique_ids
    assert {"phase_1_voltage", "phase_2_current"} <= unique_ids
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, SERIAL), mock_config_entry.entry_id
    )
    assert device.hw_version is None

    # The reading comes back without a reload.
    mock_unit.holding[0x3048] = 2300  # L2 voltage: 23.00 V
    await _next_poll(hass, freezer)
    await _next_poll(hass, freezer)

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SERIAL}_phase_2_voltage"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "23.0"


async def test_unloaded_entry_adds_no_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_unit,
) -> None:
    """A reading that recovers after the entry unloaded gets no sensor."""
    set_readings(mock_unit)
    mock_unit.holding[0x3048] = 0x7FFF  # L2 voltage: not available
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    mock_unit.holding[0x3048] = 2300
    await _next_poll(hass, freezer)

    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{SERIAL}_phase_2_voltage"
        )
        is None
    )


async def test_failed_read_at_setup_keeps_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_unit,
) -> None:
    """A sub-system that failed to read at setup still gets its sensors."""
    set_readings(mock_unit)
    mock_unit.fail_read(0x3040, IllegalDataAddressError())
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SERIAL}_phase_1_voltage"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("fine_frequency_readable", "state", "precision"),
    [(True, "50.012", 3), (False, "50.01", 2)],
)
async def test_frequency_resolution(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_unit,
    fine_frequency_readable: bool,
    state: str,
    precision: int,
) -> None:
    """The frequency is read in 0.001 Hz where the meter's firmware has it."""
    set_identity(mock_unit, VM_3P75CT)
    set_readings(mock_unit)
    if not fine_frequency_readable:
        mock_unit.fail_read(0x303E, IllegalDataAddressError())
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"VM-3P75CT ({SERIAL})",
        data={"host": "192.168.1.103", "model": "vm_3p75ct"},
        unique_id=SERIAL,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SERIAL}_frequency"
    )
    assert hass.states.get(entity_id).state == state
    options = entity_registry.async_get(entity_id).options["sensor"]
    assert options["suggested_display_precision"] == precision


async def test_fine_frequency_survives_a_failed_read_at_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_unit,
) -> None:
    """A meter with the fine frequency keeps it when its first read fails.

    The frequency has no value then, but the meter is known to have the fine
    register, so its 0.001 Hz sensor is created, not the 0.01 Hz one.
    """
    set_identity(mock_unit, VM_3P75CT)
    set_readings(mock_unit)
    mock_unit.fail_read(0x3034, IllegalDataAddressError())
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"VM-3P75CT ({SERIAL})",
        data={"host": "192.168.1.104", "model": "vm_3p75ct"},
        unique_id=SERIAL,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SERIAL}_frequency"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    options = entity_registry.async_get(entity_id).options["sensor"]
    assert options["suggested_display_precision"] == 3

    mock_unit.fail_read(0x3034, None)
    await _next_poll(hass, freezer)

    assert hass.states.get(entity_id).state == "50.012"


async def test_only_connected_phases_get_sensors(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_unit
) -> None:
    """A meter configured as single-phase gets no L2/L3 sensors.

    Its L2/L3 energy counters read a plain 0 rather than "unavailable", so only
    the phase configuration tells they aren't connected.
    """
    set_identity(mock_unit, VM_3P75CT)
    set_readings(mock_unit)
    mock_unit.holding[0x2000] = 0  # phase configuration: single phase on L1
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"VM-3P75CT ({SERIAL})",
        data={"host": "192.168.1.96", "model": "vm_3p75ct"},
        unique_id=SERIAL,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    unique_ids = {
        entry.unique_id.removeprefix(f"{SERIAL}_")
        for entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    }
    assert {uid for uid in unique_ids if uid.startswith("phase_")} == {
        "phase_1_voltage",
        "phase_1_current",
        "phase_1_power",
        "phase_1_forward_energy",
        "phase_1_reverse_energy",
    }
