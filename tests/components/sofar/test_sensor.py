"""Tests for the Sofar sensor platform."""

from collections.abc import Callable
from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)
from sofar_modbus.modern.device import SofarInverter
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.sofar.const import DOMAIN, SCAN_INTERVAL
from homeassistant.components.sofar.sensor import (
    SENSOR_DESCRIPTIONS,
    TOTAL_SENSOR_DESCRIPTIONS,
    SofarSensorDescription,
    SofarTotalSensorDescription,
)
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er, restore_state

from . import (
    MOCK_ENTRY_DATA,
    MOCK_HYBRID_MODEL,
    MOCK_HYBRID_SERIAL,
    MOCK_MODEL,
    MOCK_SERIAL,
    deny_charge_cutoff,
    refuse_battery_config_mask,
    seed_hybrid_inverter,
    seed_pv_inverter,
)

# Values the app shows, worked out from other battery_config fields.
DERIVED_KEYS = {
    "on_grid_discharge_cutoff_soc",
    "off_grid_discharge_cutoff_soc",
    "off_grid_recovery_soc",
}


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
    """Guards the descriptions against a component/key transcription slip."""
    inverter = SofarInverter(
        MockModbusConnection().for_unit(1), serial_number="SP1ES12345678"
    )
    for description in (*SENSOR_DESCRIPTIONS, *TOTAL_SENSOR_DESCRIPTIONS):
        component = getattr(inverter, description.component, None)
        assert component is not None, f"unknown component {description.component!r}"
        assert description.key in DERIVED_KEYS or hasattr(component, description.key), (
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


@pytest.mark.parametrize(
    ("serial", "model", "seed", "created", "enabled"),
    [
        pytest.param(MOCK_SERIAL, MOCK_MODEL, seed_pv_inverter, 75, 22, id="pv"),
        pytest.param(
            MOCK_HYBRID_SERIAL,
            MOCK_HYBRID_MODEL,
            seed_hybrid_inverter,
            149,
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
        for description in (*SENSOR_DESCRIPTIONS, *TOTAL_SENSOR_DESCRIPTIONS)
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


@pytest.mark.usefixtures("mock_get_unit")
async def test_total_keeps_its_restored_value_while_asleep(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a silent restart still stores the total the next one seeds from."""
    mock_config_entry.add_to_hass(hass)
    entry = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        f"{MOCK_SERIAL}_solar_generation_total",
        config_entry=mock_config_entry,
    )
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(entry.entity_id, "990.0"),
                {"native_value": 990.0, "native_unit_of_measurement": "kWh"},
            )
        ],
    )
    mock_connection.for_unit(1).fail_requests(ModbusTimeoutError("asleep"))
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entry.entity_id).state == STATE_UNAVAILABLE
    stored = {
        stored.state.entity_id: stored
        for stored in restore_state.async_get(hass).async_get_stored_states()
    }
    extra_data = stored[entry.entity_id].extra_data
    assert extra_data is not None
    assert extra_data.as_dict()["native_value"] == 990.0


async def test_sensor_availability_on_component_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test a sensor follows its own component, not the whole poll."""
    grid_frequency_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{MOCK_SERIAL}_grid_frequency"
    )
    pv_power_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{MOCK_SERIAL}_pv_power_1"
    )
    assert grid_frequency_id is not None
    assert pv_power_id is not None

    unit = mock_connection.for_unit(1)
    unit.fail_read(0x0484, ModbusTimeoutError("stuck"))
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(grid_frequency_id).state == STATE_UNAVAILABLE
    assert hass.states.get(pv_power_id).state == "2.5"

    unit.fail_read(0x0484, None)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(grid_frequency_id).state == "50.0"


@pytest.mark.parametrize(
    "description",
    [
        pytest.param(description, id=description.key)
        for description in SENSOR_DESCRIPTIONS
        if description.key not in DERIVED_KEYS
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
    ("key", "values", "expected"),
    [
        pytest.param(
            "on_grid_discharge_cutoff_soc",
            {"bat_config_depth_of_discharge": 73},
            27,
            id="on_grid",
        ),
        pytest.param(
            "on_grid_discharge_cutoff_soc",
            {"bat_config_depth_of_discharge": None},
            None,
            id="on_grid_unread",
        ),
        pytest.param(
            "off_grid_discharge_cutoff_soc",
            {"bat_config_end_of_discharge": 90},
            10,
            id="off_grid",
        ),
        pytest.param(
            "off_grid_discharge_cutoff_soc",
            {"bat_config_end_of_discharge": None},
            None,
            id="off_grid_unread",
        ),
        pytest.param(
            "off_grid_recovery_soc",
            {"bat_config_end_of_discharge": 90, "bat_config_eps_buffer": 5},
            15,
            id="recovery",
        ),
        pytest.param(
            "off_grid_recovery_soc",
            {"bat_config_end_of_discharge": None, "bat_config_eps_buffer": 5},
            None,
            id="recovery_end_of_discharge_unread",
        ),
        pytest.param(
            "off_grid_recovery_soc",
            {"bat_config_end_of_discharge": 90, "bat_config_eps_buffer": None},
            None,
            id="recovery_eps_buffer_unread",
        ),
    ],
)
async def test_derived_cutoff_soc(
    init_integration: MockConfigEntry,
    key: str,
    values: dict[str, int | None],
    expected: int | None,
) -> None:
    """Test cut-off sensors show what the SofarCloud app shows."""
    device = init_integration.runtime_data.readings.device
    with patch.dict(device.battery_config._values, values):
        assert (
            next(d for d in SENSOR_DESCRIPTIONS if d.key == key).value_fn(device)
            == expected
        )


@pytest.mark.parametrize(
    "hide_charge_cutoff",
    [
        pytest.param(deny_charge_cutoff, id="mask_denies"),
        pytest.param(refuse_battery_config_mask, id="no_mask"),
    ],
)
async def test_charge_cutoff_needs_a_declaring_mask(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hide_charge_cutoff: Callable[[MockModbusUnit], None],
) -> None:
    """Test a hybrid gets no charge cut-off unless its mask declares it."""
    connection = MockModbusConnection()
    unit = connection.for_unit(1)
    seed_hybrid_inverter(unit)
    hide_charge_cutoff(unit)
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

    assert (
        entity_registry.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, f"{MOCK_HYBRID_SERIAL}_bat_config_charge_cutoff_soc"
        )
        is None
    )
    # The rest of the battery config does not need the mask.
    assert (
        entity_registry.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, f"{MOCK_HYBRID_SERIAL}_on_grid_discharge_cutoff_soc"
        )
        is not None
    )


@pytest.mark.parametrize(
    "description",
    [
        pytest.param(description, id=description.key)
        for description in TOTAL_SENSOR_DESCRIPTIONS
    ],
)
async def test_total_fn_reads_the_total_its_key_names(
    init_integration: MockConfigEntry, description: SofarTotalSensorDescription
) -> None:
    """Test each total_fn hands out the corrected total its key names."""
    device = init_integration.runtime_data.readings.device
    total = description.total_fn(device)
    assert total.component is getattr(device, description.component)
    assert total.name == description.key
