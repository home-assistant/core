"""Tests for the Sofar sensor platform."""

from collections.abc import Callable
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest
from sofar_modbus.modern.device import SofarInverter
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorStateClass
from homeassistant.components.sofar.const import DOMAIN, SCAN_INTERVAL
from homeassistant.components.sofar.sensor import (
    SENSOR_DESCRIPTIONS,
    SofarSensor,
    SofarSensorDescription,
    SofarTotalSensor,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    MOCK_ENTRY_DATA,
    MOCK_HYBRID_MODEL,
    MOCK_HYBRID_SERIAL,
    MOCK_MODEL,
    MOCK_SERIAL,
    seed_hybrid_inverter,
    seed_pv_inverter,
)

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities match their snapshot on a hybrid device."""
    connection = MockModbusConnection()
    seed_hybrid_inverter(connection.for_unit(1))
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_HYBRID_SERIAL,
        data=MOCK_ENTRY_DATA,
        title=MOCK_HYBRID_MODEL,
    )
    entry.add_to_hass(hass)
    with (
        patch("homeassistant.components.sofar.PLATFORMS", [Platform.SENSOR]),
        patch(
            "homeassistant.components.sofar.async_get_unit",
            side_effect=lambda hass, entry, params, unit_id: connection.for_unit(
                unit_id
            ),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


def test_sensor_description_components_are_real() -> None:
    """Guards SENSOR_DESCRIPTIONS against a component/key transcription slip."""
    inverter = SofarInverter(
        MockModbusConnection().for_unit(1), serial_number="SP1ES12345678"
    )
    for description in SENSOR_DESCRIPTIONS:
        component = getattr(inverter, description.component, None)
        assert component is not None, f"unknown component {description.component!r}"
        assert hasattr(component, description.key), (
            f"{description.component}.{description.key} does not exist"
        )


async def test_sensor_entities_created_and_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test a measurement and an enum sensor report live state."""
    grid_freq_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, "sofar", f"{MOCK_SERIAL}_grid_frequency"
    )
    assert grid_freq_id is not None
    assert (state := hass.states.get(grid_freq_id)) is not None
    assert float(state.state) == 50.0

    system_state_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, "sofar", f"{MOCK_SERIAL}_system_state"
    )
    assert system_state_id is not None
    assert (state := hass.states.get(system_state_id)) is not None
    assert state.state == "grid_connected"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("key", "address", "raw", "expected"),
    [
        pytest.param("system_state", 0x0404, 0, "waiting", id="system_state-waiting"),
        pytest.param("system_state", 0x0404, 1, "checking", id="system_state-checking"),
        pytest.param(
            "system_state",
            0x0404,
            2,
            "grid_connected",
            id="system_state-grid_connected",
        ),
        pytest.param(
            "system_state",
            0x0404,
            3,
            "emergency_power_supply",
            id="system_state-emergency_power_supply",
        ),
        pytest.param(
            "system_state",
            0x0404,
            4,
            "recoverable_fault",
            id="system_state-recoverable_fault",
        ),
        pytest.param(
            "system_state",
            0x0404,
            5,
            "permanent_fault",
            id="system_state-permanent_fault",
        ),
        pytest.param(
            "system_state", 0x0404, 6, "upgrading", id="system_state-upgrading"
        ),
        pytest.param(
            "system_state", 0x0404, 7, "self_charging", id="system_state-self_charging"
        ),
        pytest.param(
            "system_state", 0x0404, 8, "svg_state", id="system_state-svg_state"
        ),
        pytest.param(
            "system_state", 0x0404, 9, "pid_state", id="system_state-pid_state"
        ),
        pytest.param(
            "bat_config_protocol",
            0x1046,
            0,
            "first_flight_built_in_bms_default",
            id="bat_config_protocol-first_flight_built_in_bms_default",
        ),
        pytest.param(
            "bat_config_protocol",
            0x1046,
            1,
            "pie_energy_protocol_pylon",
            id="bat_config_protocol-pie_energy_protocol_pylon",
        ),
        pytest.param(
            "bat_config_protocol",
            0x1046,
            2,
            "first_flight_protocol_general",
            id="bat_config_protocol-first_flight_protocol_general",
        ),
        pytest.param(
            "bat_config_protocol", 0x1046, 3, "amass", id="bat_config_protocol-amass"
        ),
        pytest.param(
            "bat_config_protocol", 0x1046, 4, "lg", id="bat_config_protocol-lg"
        ),
        pytest.param(
            "bat_config_protocol",
            0x1046,
            5,
            "alphaess",
            id="bat_config_protocol-alphaess",
        ),
        pytest.param(
            "bat_config_protocol", 0x1046, 6, "catl", id="bat_config_protocol-catl"
        ),
        pytest.param(
            "bat_config_protocol", 0x1046, 7, "weco", id="bat_config_protocol-weco"
        ),
        pytest.param(
            "bat_config_protocol", 0x1046, 8, "fronus", id="bat_config_protocol-fronus"
        ),
        pytest.param(
            "bat_config_protocol", 0x1046, 9, "ems", id="bat_config_protocol-ems"
        ),
        pytest.param(
            "bat_config_protocol", 0x1046, 10, "nilar", id="bat_config_protocol-nilar"
        ),
        pytest.param(
            "bat_config_protocol", 0x1046, 11, "bts_5k", id="bat_config_protocol-bts_5k"
        ),
        pytest.param(
            "bat_config_protocol",
            0x1046,
            12,
            "move_for",
            id="bat_config_protocol-move_for",
        ),
        pytest.param(
            "bat_config_cell_type",
            0x1051,
            0,
            "lead_acid",
            id="bat_config_cell_type-lead_acid",
        ),
        pytest.param(
            "bat_config_cell_type",
            0x1051,
            1,
            "lithium_iron_phosphate",
            id="bat_config_cell_type-lithium_iron_phosphate",
        ),
        pytest.param(
            "bat_config_cell_type",
            0x1051,
            2,
            "ternary",
            id="bat_config_cell_type-ternary",
        ),
        pytest.param(
            "bat_config_cell_type",
            0x1051,
            3,
            "lithium_titanate",
            id="bat_config_cell_type-lithium_titanate",
        ),
        pytest.param(
            "bat_config_cell_type", 0x1051, 4, "agm", id="bat_config_cell_type-agm"
        ),
        pytest.param(
            "bat_config_cell_type", 0x1051, 5, "gel", id="bat_config_cell_type-gel"
        ),
        pytest.param(
            "bat_config_cell_type",
            0x1051,
            6,
            "flooded",
            id="bat_config_cell_type-flooded",
        ),
        pytest.param(
            "sync_rtc_result", 0x100A, 0, "successful", id="sync_rtc_result-successful"
        ),
        pytest.param(
            "sync_rtc_result",
            0x100A,
            1,
            "operation_in_progress",
            id="sync_rtc_result-operation_in_progress",
        ),
        pytest.param(
            "sync_rtc_result",
            0x100A,
            2,
            "enabled_discharging",
            id="sync_rtc_result-enabled_discharging",
        ),
        pytest.param(
            "sync_rtc_result", 0x100A, 4, "disabled", id="sync_rtc_result-disabled"
        ),
        pytest.param(
            "sync_rtc_result",
            0x100A,
            65531,
            "operation_failed_controller_refused_to_respond",
            id="sync_rtc_result-operation_failed_controller_refused_to_respond",
        ),
        pytest.param(
            "sync_rtc_result",
            0x100A,
            65532,
            "operation_failed_no_response_from_the_controller",
            id="sync_rtc_result-operation_failed_no_response_from_the_controller",
        ),
        pytest.param(
            "sync_rtc_result",
            0x100A,
            65533,
            "operation_failed_current_function_disabled",
            id="sync_rtc_result-operation_failed_current_function_disabled",
        ),
        pytest.param(
            "sync_rtc_result",
            0x100A,
            65534,
            "operation_failed_parameter_access_failed",
            id="sync_rtc_result-operation_failed_parameter_access_failed",
        ),
        pytest.param(
            "sync_rtc_result",
            0x100A,
            65535,
            "operation_failed_input_parameters_incorrect",
            id="sync_rtc_result-operation_failed_input_parameters_incorrect",
        ),
    ],
)
async def test_enum_sensor_reports_every_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    key: str,
    address: int,
    raw: int,
    expected: str,
) -> None:
    """Test each enum sensor reports every state its register holds."""
    connection = MockModbusConnection()
    unit = connection.for_unit(1)
    seed_hybrid_inverter(unit)
    unit.holding[address] = raw
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_HYBRID_SERIAL,
        data=MOCK_ENTRY_DATA,
        title=MOCK_HYBRID_MODEL,
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.sofar.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: connection.for_unit(unit_id),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    entity_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{MOCK_HYBRID_SERIAL}_{key}"
    )
    assert entity_id is not None
    assert (state := hass.states.get(entity_id)) is not None
    assert state.state == expected


@pytest.mark.parametrize(
    ("serial", "model", "seed", "created", "enabled"),
    [
        pytest.param(MOCK_SERIAL, MOCK_MODEL, seed_pv_inverter, 74, 21, id="pv"),
        pytest.param(
            MOCK_HYBRID_SERIAL,
            MOCK_HYBRID_MODEL,
            seed_hybrid_inverter,
            145,
            44,
            id="hybrid",
        ),
    ],
)
async def test_enabled_by_default_partition(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    serial: str,
    model: str,
    seed: Callable[[MockModbusUnit], None],
    created: int,
    enabled: int,
) -> None:
    """Test the opt-in tiering holds, and matches the descriptions."""
    connection = MockModbusConnection()
    seed(connection.for_unit(1))
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=serial, data=MOCK_ENTRY_DATA, title=model
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.sofar.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: connection.for_unit(unit_id),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    entries = [
        e
        for e in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        if e.domain == SENSOR_DOMAIN
    ]
    # Literal counts: an accidental flip has to be acknowledged here.
    assert len(entries) == created
    assert len([e for e in entries if e.disabled_by is None]) == enabled

    served = entry.runtime_data.served_components
    expected_disabled = {
        description.key
        for description in SENSOR_DESCRIPTIONS
        if description.component in served
        and not description.entity_registry_enabled_default
    }
    disabled = {
        registry_entry.unique_id.removeprefix(f"{serial}_")
        for registry_entry in entries
        if registry_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    }
    assert disabled == expected_disabled


async def test_settings_backed_sensor_created_and_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a settings-polled component reaches the sensor platform."""
    connection = MockModbusConnection()
    seed_hybrid_inverter(connection.for_unit(1))
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_HYBRID_SERIAL,
        data=MOCK_ENTRY_DATA,
        title=MOCK_HYBRID_MODEL,
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.sofar.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: connection.for_unit(unit_id),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    rtc_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, "sofar", f"{MOCK_HYBRID_SERIAL}_sync_rtc_result"
    )
    assert rtc_id is not None
    assert (state := hass.states.get(rtc_id)) is not None
    assert state.state == "successful"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_enum_option_slugs_are_translation_keys(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test acronym enum members become slugs, not capitalized words."""
    connection = MockModbusConnection()
    seed_hybrid_inverter(connection.for_unit(1))
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_HYBRID_SERIAL,
        data=MOCK_ENTRY_DATA,
        title=MOCK_HYBRID_MODEL,
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.sofar.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: connection.for_unit(unit_id),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    protocol_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, "sofar", f"{MOCK_HYBRID_SERIAL}_bat_config_protocol"
    )
    assert protocol_id is not None
    assert (state := hass.states.get(protocol_id)) is not None
    assert "lg" in state.attributes["options"]
    assert "catl" in state.attributes["options"]


async def test_shipped_sensors_created_and_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the four shipped sensors are created with the right values."""
    pv_power_1_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, "sofar", f"{MOCK_SERIAL}_pv_power_1"
    )
    pv_power_2_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, "sofar", f"{MOCK_SERIAL}_pv_power_2"
    )
    pv_power_total_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, "sofar", f"{MOCK_SERIAL}_pv_power_total"
    )
    solar_generation_total_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, "sofar", f"{MOCK_SERIAL}_solar_generation_total"
    )
    assert pv_power_1_id is not None
    assert pv_power_2_id is not None
    assert pv_power_total_id is not None
    assert solar_generation_total_id is not None

    assert (state := hass.states.get(pv_power_1_id)) is not None
    assert float(state.state) == 2.5
    assert (state := hass.states.get(pv_power_2_id)) is not None
    assert float(state.state) == 1.8
    assert (state := hass.states.get(pv_power_total_id)) is not None
    assert float(state.state) == 4.3
    assert (state := hass.states.get(solar_generation_total_id)) is not None
    assert float(state.state) == 15.0


async def test_total_sensor_restore_data_parsing(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test SofarTotalSensor restore parsing: valid, invalid, and None."""
    runtime_data = init_integration.runtime_data
    device = runtime_data.readings.device
    description = SofarSensorDescription(
        key="load_consumption_total",
        component="meter_energy",
        translation_key="load_consumption_total",
        value_fn=lambda device: device.meter_energy.load_consumption_total,
    )

    device.meter_energy.load_consumption_total = None
    sensor = SofarTotalSensor(runtime_data, description)
    sensor.hass = hass
    sensor.async_get_last_sensor_data = AsyncMock(
        return_value=SimpleNamespace(native_value="555.5")
    )
    await sensor.async_added_to_hass()
    assert sensor.native_value == 555.5

    invalid_sensor = SofarTotalSensor(runtime_data, description)
    invalid_sensor.hass = hass
    invalid_sensor.async_get_last_sensor_data = AsyncMock(
        return_value=SimpleNamespace(native_value="not_a_number")
    )
    await invalid_sensor.async_added_to_hass()
    assert invalid_sensor.native_value is None

    blank_sensor = SofarTotalSensor(runtime_data, description)
    blank_sensor.hass = hass
    blank_sensor.async_get_last_sensor_data = AsyncMock(
        return_value=SimpleNamespace(native_value=None)
    )
    await blank_sensor.async_added_to_hass()
    assert blank_sensor.native_value is None

    device.meter_energy.load_consumption_total = 120.0
    total_sensor = SofarTotalSensor(runtime_data, description)
    assert total_sensor.native_value == 120.0

    device.meter_energy.load_consumption_total = None
    unset_sensor = SofarTotalSensor(runtime_data, description)
    assert unset_sensor.native_value is None


async def test_total_sensor_seeds_high_water_from_restored_value(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test a restored value seeds the library's high-water mark."""
    runtime_data = init_integration.runtime_data
    device = runtime_data.readings.device
    description = SofarSensorDescription(
        key="load_consumption_total",
        component="meter_energy",
        translation_key="load_consumption_total",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda device: (
            device.meter_energy.load_consumption_total_corrected.value
        ),
        total_fn=lambda device: device.meter_energy.load_consumption_total_corrected,
    )
    sensor = SofarTotalSensor(runtime_data, description)
    sensor.hass = hass
    sensor.async_get_last_sensor_data = AsyncMock(
        return_value=SimpleNamespace(native_value="555.5")
    )
    with patch.object(device.meter_energy, "seed_high_water") as mock_seed:
        await sensor.async_added_to_hass()
    mock_seed.assert_called_once_with("load_consumption_total", 555.5)


async def test_sensor_dead_link_unavailable(init_integration: MockConfigEntry) -> None:
    """Test SofarSensor.available is False when the last update failed."""
    runtime_data = init_integration.runtime_data
    description = SofarSensorDescription(
        key="grid_frequency",
        component="grid",
        translation_key="grid_frequency",
        value_fn=lambda device: device.grid.grid_frequency,
    )
    sensor = SofarSensor(runtime_data, description)
    assert sensor.native_value == 50.0
    runtime_data.readings.last_update_success = False
    assert not sensor.available


async def test_total_sensor_dead_link_unavailable(
    init_integration: MockConfigEntry,
) -> None:
    """Test a total stops reporting a stale value once the link dies."""
    runtime_data = init_integration.runtime_data
    description = SofarSensorDescription(
        key="load_consumption_total",
        component="meter_energy",
        translation_key="load_consumption_total",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda device: (
            device.meter_energy.load_consumption_total_corrected.value
        ),
        total_fn=lambda device: device.meter_energy.load_consumption_total_corrected,
    )
    sensor = SofarTotalSensor(runtime_data, description)
    assert sensor.available

    runtime_data.readings.last_update_success = False
    assert not sensor.available


async def test_sensor_availability_on_component_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test SofarSensor.available reflects its own component, not the link."""
    runtime_data = init_integration.runtime_data
    description = SofarSensorDescription(
        key="grid_frequency",
        component="grid",
        translation_key="grid_frequency",
        value_fn=lambda device: device.grid.grid_frequency,
    )
    sensor = SofarSensor(runtime_data, description)
    assert sensor.available

    unit = mock_connection.for_unit(1)
    unit.fail_read(0x0484, ModbusTimeoutError("stuck"))
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert not sensor.available

    unit.fail_read(0x0484, None)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert sensor.available


async def test_total_sensor_total_increasing_uses_corrected_value(
    init_integration: MockConfigEntry,
) -> None:
    """Test a TOTAL_INCREASING description reads corrected() from the library."""
    runtime_data = init_integration.runtime_data
    description = SofarSensorDescription(
        key="load_consumption_total",
        component="meter_energy",
        translation_key="load_consumption_total",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda device: (
            device.meter_energy.load_consumption_total_corrected.value
        ),
        total_fn=lambda device: device.meter_energy.load_consumption_total_corrected,
    )
    device = runtime_data.readings.device
    sensor = SofarTotalSensor(runtime_data, description)
    with patch.object(
        device.meter_energy, "corrected", return_value=42.0
    ) as mock_corrected:
        assert sensor.native_value == 42.0
    mock_corrected.assert_called_once_with("load_consumption_total")
    assert sensor.available


@pytest.mark.parametrize(
    "description",
    [
        pytest.param(description, id=description.key)
        for description in SENSOR_DESCRIPTIONS
        if description.state_class is not SensorStateClass.TOTAL_INCREASING
    ],
)
async def test_value_fn_reads_the_field_its_key_names(
    init_integration: MockConfigEntry, description: SofarSensorDescription
) -> None:
    """Test each value_fn reads the field its key and component name."""
    device = init_integration.runtime_data.readings.device
    component = getattr(device, description.component)
    sentinel = object()
    with patch.dict(component._values, {description.key: sentinel}):
        assert description.value_fn(device) is sentinel


@pytest.mark.parametrize(
    "description",
    [
        pytest.param(description, id=description.key)
        for description in SENSOR_DESCRIPTIONS
        if description.state_class is SensorStateClass.TOTAL_INCREASING
    ],
)
async def test_total_reads_and_seeds_its_own_corrected_total(
    init_integration: MockConfigEntry, description: SofarSensorDescription
) -> None:
    """Test each total reads and seeds the corrected total its key names."""
    device = init_integration.runtime_data.readings.device
    component = getattr(device, description.component)
    with patch.object(component, "corrected", return_value=42.0) as mock_corrected:
        assert description.value_fn(device) == 42.0
    mock_corrected.assert_called_once_with(description.key)
    assert description.total_fn is not None
    assert description.total_fn(device).name == description.key
