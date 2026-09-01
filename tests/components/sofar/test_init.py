"""Test the Sofar Inverter Modbus integration setup and unload."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusConnectionError, ModbusError, ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.sofar.const import (
    DOMAIN,
    SCAN_INTERVAL,
    SETTINGS_SCAN_INTERVAL,
)
from homeassistant.components.sofar.coordinator import SofarRuntimeData
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import (
    MOCK_HW_VERSION,
    MOCK_HYBRID_MODEL,
    MOCK_HYBRID_SERIAL,
    MOCK_SERIAL,
    MOCK_SW_VERSION,
    MOCK_USER_INPUT,
    seed_hybrid_inverter,
)

from tests.common import MockConfigEntry, async_fire_time_changed

PV_POWER_REGISTER = 0x0586
BATTERY_3_VOLTAGE_REGISTER = 0x0612
SOLAR_GENERATION_REGISTER = 0x0684


def _heal_after_one_failure(unit: MockModbusUnit, address: int) -> None:
    """Fail a register once, so the coordinator's retry finds it healthy."""
    unit.fail_read(address, ModbusError("busy"))
    read = unit.read_holding_registers

    async def read_and_heal(address_: int, count: int) -> list[int]:
        try:
            return await read(address_, count)
        except ModbusError:
            unit.fail_read(address, None)
            raise

    unit.read_holding_registers = read_and_heal


def _drop_link_after_one_failure(unit: MockModbusUnit, address: int) -> None:
    """Fail the last component, then the link, so its retry finds it dead."""
    unit.fail_read(address, ModbusError("busy"))
    read = unit.read_holding_registers

    async def read_and_drop(address_: int, count: int) -> list[int]:
        try:
            return await read(address_, count)
        except ModbusError:
            unit.fail_requests(ModbusConnectionError("link dropped"))
            raise

    unit.read_holding_registers = read_and_drop


async def test_setup_and_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test a config entry sets up and unloads with runtime_data populated."""
    entry = init_integration
    assert entry.state is ConfigEntryState.LOADED
    assert isinstance(entry.runtime_data, SofarRuntimeData)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_removes_the_stale_waiting_time_entity(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an upgrade drops the removed waiting-time entity too."""
    mock_config_entry.add_to_hass(hass)
    entry = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        f"{MOCK_SERIAL}_waiting_time",
        config_entry=mock_config_entry,
    )

    with patch(
        "homeassistant.components.sofar.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entity_registry.async_get(entry.entity_id) is None


async def test_setup_entry_unrecognized_inverter_raises_setup_error(
    hass: HomeAssistant,
) -> None:
    """Test setup fails permanently (no retry) for an unrecognized serial."""
    # Not reachable via the config flow; covers an existing entry
    # outliving a sofar-modbus library downgrade. Caught before any
    # Modbus I/O, so no connection needs mocking here.
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="UNRECOGNIZED_SERIAL_XYZ", data=MOCK_USER_INPUT
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_unreachable_link_retries_and_recovers(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a dead link on first refresh retries setup, then recovers."""
    mock_config_entry.add_to_hass(hass)
    unit = mock_connection.for_unit(1)
    unit.fail_requests(ModbusTimeoutError("stuck"))

    with patch(
        "homeassistant.components.sofar.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

        unit.fail_requests(None)
        freezer.tick(timedelta(seconds=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_settings_failure_does_not_block_reading_sensors(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a settings-block failure still lets reading sensors set up."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.sofar.async_get_unit",
            side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
                unit_id
            ),
        ),
        patch(
            "sofar_modbus.modern.device.SofarInverter.async_update_settings",
            side_effect=ModbusConnectionError("settings unreachable"),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.async_entity_ids("sensor")
    assert mock_config_entry.runtime_data.settings.last_update_success is False


async def test_settings_recover_without_a_reload(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the settings coordinator recovers on its own once the link heals."""
    connection = MockModbusConnection()
    seed_hybrid_inverter(connection.for_unit(1))
    unit = connection.for_unit(1)
    # A settings-only register, so the readings poll still sets up.
    unit.fail_read(0x1105, ModbusConnectionError("settings unreachable"))
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_HYBRID_SERIAL,
        data=MOCK_USER_INPUT,
        title=MOCK_HYBRID_MODEL,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.sofar.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: connection.for_unit(unit_id),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.runtime_data.settings.last_update_success is False

    unit.fail_read(0x1105, None)
    freezer.tick(timedelta(seconds=SETTINGS_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert entry.runtime_data.settings.last_update_success is True


async def test_sensor_platform_is_forwarded(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the sensor platform is set up as part of config entry setup."""
    assert hass.states.async_entity_ids("sensor")


async def test_device_info_carries_the_firmware_versions(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the identity registers reach the device, not the state machine."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL), init_integration.entry_id
    )

    assert device is not None
    assert device.hw_version == MOCK_HW_VERSION
    assert device.sw_version == MOCK_SW_VERSION
    assert device.serial_number == MOCK_SERIAL


async def test_device_versions_need_a_reload_to_recover(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a failed identity read is not retried until the entry reloads."""
    connection = MockModbusConnection()
    seed_hybrid_inverter(connection.for_unit(1))
    unit = connection.for_unit(1)
    # Inside the identity block, so the whole component fails to read.
    unit.fail_read(0x044D, ModbusConnectionError("identity unreachable"))
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_HYBRID_SERIAL,
        data=MOCK_USER_INPUT,
        title=MOCK_HYBRID_MODEL,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.sofar.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: connection.for_unit(unit_id),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, MOCK_HYBRID_SERIAL), entry.entry_id
        )
        assert device is not None
        assert device.hw_version is None
        assert device.sw_version is None

        unit.fail_read(0x044D, None)
        freezer.tick(timedelta(seconds=SETTINGS_SCAN_INTERVAL))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, MOCK_HYBRID_SERIAL), entry.entry_id
        )
        assert device is not None
        assert device.hw_version is None

        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_HYBRID_SERIAL), entry.entry_id
    )
    assert device is not None
    assert device.hw_version == MOCK_HW_VERSION
    assert device.sw_version == MOCK_SW_VERSION


async def test_identity_retries_after_one_failure(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a transient identity failure is retried within the same setup."""
    mock_config_entry.add_to_hass(hass)
    unit = mock_connection.for_unit(1)
    _heal_after_one_failure(unit, 0x044D)

    with patch(
        "homeassistant.components.sofar.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.hw_version == MOCK_HW_VERSION


async def test_every_component_failing_recovers_on_a_later_poll(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    entity_registry: er.EntityRegistry,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test sensors go unavailable while no component answers, then return."""
    entity_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{MOCK_SERIAL}_pv_power_1"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "2.5"

    mock_connection.for_unit(1).fail_requests(ModbusError("illegal data address"))
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    # Availability alone cannot tell a failed poll from one that reported
    # every component as failed; only the logged error separates them.
    assert "no component answered" in caplog.text

    mock_connection.for_unit(1).fail_requests(None)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "2.5"


async def test_component_answering_the_retry_stays_available(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test one component failing alone is retried and keeps its sensors."""
    unit = mock_connection.for_unit(1)
    entity_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{MOCK_SERIAL}_pv_power_1"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "2.5"

    # A new value only reaches the sensor if the retry actually read it;
    # a component left failed would keep showing the old one.
    unit.holding[PV_POWER_REGISTER] = 300
    _heal_after_one_failure(unit, PV_POWER_REGISTER)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "3.0"


async def test_link_dying_during_the_retry_marks_sensors_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test a link lost while retrying one component fails the whole poll."""
    unit = mock_connection.for_unit(1)
    _drop_link_after_one_failure(unit, SOLAR_GENERATION_REGISTER)

    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{MOCK_SERIAL}_grid_frequency"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_pv_strings_become_their_own_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test every PV string the inverter serves gets a device of its own."""
    inverter = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL), init_integration.entry_id
    )
    assert inverter is not None

    strings = [
        device
        for device in dr.async_entries_for_config_entry(
            device_registry, init_integration.entry_id
        )
        if device.via_device_id == inverter.id
    ]

    # Two MPPTs on this model, so strings 3 to 10 are not served at all.
    assert {device.name for device in strings} == {"PV string 1", "PV string 2"}


async def test_pv_aggregate_stays_on_the_inverter(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test a total living in a per-string component is not moved off."""
    inverter = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL), init_integration.entry_id
    )
    assert inverter is not None

    # pv_power_total sits in the pv_1_2 component but measures all strings.
    entity_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{MOCK_SERIAL}_pv_power_total"
    )
    assert entity_id is not None
    assert entity_registry.async_get(entity_id).device_id == inverter.id


async def test_only_wired_battery_packs_become_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test packs are counted by what answers, not by the register map."""
    connection = MockModbusConnection()
    seed_hybrid_inverter(connection.for_unit(1))
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_HYBRID_SERIAL,
        data=MOCK_USER_INPUT,
        title=MOCK_HYBRID_MODEL,
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.sofar.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: connection.for_unit(unit_id),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    inverter = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_HYBRID_SERIAL), entry.entry_id
    )
    assert inverter is not None
    battery_names = {
        device.name
        for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        if device.via_device_id == inverter.id and device.name.startswith("Battery")
    }

    # The seed wires packs 1 and 3; the map allows 8, so the rest must not.
    assert battery_names == {"Battery 1", "Battery 3"}
    assert (
        entity_registry.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, f"{MOCK_HYBRID_SERIAL}_battery_voltage_2"
        )
        is None
    )

    inverter = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_HYBRID_SERIAL), entry.entry_id
    )
    assert inverter is not None
    # A combined total is the inverter's, not any one pack's.
    total_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{MOCK_HYBRID_SERIAL}_battery_capacity_total"
    )
    assert total_id is not None
    assert entity_registry.async_get(total_id).device_id == inverter.id


async def test_total_survives_a_torn_first_poll_after_reload(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a reload's first poll is protected by the pre-reload total."""
    mock_config_entry.add_to_hass(hass)
    unit = mock_connection.for_unit(1)
    unit.holding[0x068A] = 0
    unit.holding[0x068B] = 10000  # load_consumption_total -> 1000.0 kWh

    with patch(
        "homeassistant.components.sofar.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

        entity_id = entity_registry.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, f"{MOCK_SERIAL}_load_consumption_total"
        )
        assert entity_id is not None
        assert hass.states.get(entity_id).state == "1000.0"

        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # A torn read on the reload's first poll, inside the 1% dip band.
        unit.holding[0x068B] = 9995

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == "1000.0"


async def test_battery_pack_appears_once_its_block_answers(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a pack whose block failed at setup is added when it recovers."""
    connection = MockModbusConnection()
    unit = connection.for_unit(1)
    seed_hybrid_inverter(unit)
    # Inside the battery_3_8 block, so pack 3 cannot be seen at setup.
    unit.fail_read(BATTERY_3_VOLTAGE_REGISTER, ModbusError("block busy"))

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_HYBRID_SERIAL,
        data=MOCK_USER_INPUT,
        title=MOCK_HYBRID_MODEL,
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.sofar.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: connection.for_unit(unit_id),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    unique_id = f"{MOCK_HYBRID_SERIAL}_battery_voltage_3"
    assert entity_registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, unique_id) is None

    unit.fail_read(BATTERY_3_VOLTAGE_REGISTER, None)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # No reload: the coordinator's own listener notices the pack answering.
    entity_id = entity_registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, unique_id)
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "51.5"
