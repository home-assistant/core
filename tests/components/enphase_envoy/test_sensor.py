"""Test Enphase Envoy sensors."""

import itertools
from unittest.mock import AsyncMock

from pyenphase.const import PHASENAMES
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy.const import Platform
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import TemperatureConverter

from tests.common import MockConfigEntry
from tests.components.enphase_envoy import setup_with_selected_platforms
from tests.components.enphase_envoy.conftest import ALL_FIXTURES, SENSOR_FIXTURES


@pytest.mark.parametrize(
    ("mock_envoy", "entity_count"), *SENSOR_FIXTURES, indirect=["mock_envoy"]
)
async def test_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    mock_envoy: AsyncMock,
    entity_registry: AsyncMock,
    entity_count: int,
) -> None:
    """Test enphase_envoy sensor entities."""
    await setup_with_selected_platforms(hass, config_entry, [Platform.SENSOR])

    # number entities states should be created from test data
    assert len(hass.states.async_all()) == entity_count

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

    if entity_count == 0:
        assert len(entity_entries) == 0
    else:
        # compare registered entities against snapshot of prior run
        assert entity_entries
        for entity_entry in entity_entries:
            assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
            assert hass.states.get(entity_entry.entity_id) == snapshot(
                name=f"{entity_entry.entity_id}-state"
            )


@pytest.mark.parametrize(("mock_envoy"), *ALL_FIXTURES, indirect=["mock_envoy"])
async def test_sensor_production_consumption_data(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_envoy: AsyncMock,
    entity_registry: AsyncMock,
    serial_number,
) -> None:
    """Test enphase_envoy production entities values and names."""
    await setup_with_selected_platforms(hass, config_entry, [Platform.SENSOR])
    assert entity_registry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    if len(entity_entries) == 0:
        # no entities to test with, other tests test this
        return

    entity_status = {}
    for entity_entry in entity_entries:
        entity_status[entity_entry.entity_id] = entity_entry.disabled_by

    entity_base = f"{Platform.SENSOR}.envoy_{serial_number}"

    PRODUCTION_NAMES = (
        "current_power_production",
        "energy_production_today",
        "energy_production_last_seven_days",
        "lifetime_energy_production",
    )
    data = mock_envoy.data.system_production
    PRODUCTION_TARGETS = (
        data.watts_now / 1000.0,
        data.watt_hours_today / 1000.0,
        data.watt_hours_last_7_days / 1000.0,
        data.watt_hours_lifetime / 1000000.0,
    )

    # production sensors is bare minimum and should be defined
    for name, target in zip(PRODUCTION_NAMES, PRODUCTION_TARGETS):
        assert target == float(hass.states.get(f"{entity_base}_{name}").state)

    CONSUMPTION_NAMES = (
        "current_power_consumption",
        "energy_consumption_today",
        "energy_consumption_last_seven_days",
        "lifetime_energy_consumption",
    )

    if mock_envoy.data.system_consumption:
        # if consumption is available these should be defined
        data = mock_envoy.data.system_consumption
        CONSUMPTION_TARGETS = (
            data.watts_now / 1000.0,
            data.watt_hours_today / 1000.0,
            data.watt_hours_last_7_days / 1000.0,
            data.watt_hours_lifetime / 1000000.0,
        )
        for name, target in zip(CONSUMPTION_NAMES, CONSUMPTION_TARGETS):
            assert target == float(hass.states.get(f"{entity_base}_{name}").state)

    if not mock_envoy.data.system_consumption:
        # these should not be defined if no consumption is reported
        for name in CONSUMPTION_NAMES:
            assert f"{entity_base}_{name}" not in entity_status

    PRODUCTION_PHASE_NAMES = [
        f"{name}_{phase.lower()}" for phase in PHASENAMES for name in PRODUCTION_NAMES
    ]

    if mock_envoy.data.system_production_phases:
        PRODUCTION_PHASE_TARGET = list(
            itertools.chain(
                *[
                    (
                        phase_data.watts_now / 1000.0,
                        phase_data.watt_hours_today / 1000.0,
                        phase_data.watt_hours_last_7_days / 1000.0,
                        phase_data.watt_hours_lifetime / 1000000.0,
                    )
                    for phase, phase_data in mock_envoy.data.system_production_phases.items()
                ]
            )
        )

        for name, target in zip(PRODUCTION_PHASE_NAMES, PRODUCTION_PHASE_TARGET):
            assert target == float(hass.states.get(f"{entity_base}_{name}").state)

    if not mock_envoy.data.system_production_phases:
        # these should not be defined if no phase data is reported
        for name in PRODUCTION_PHASE_NAMES:
            assert f"{entity_base}_{name}" not in entity_status

    CONSUMPTION_PHASE_NAMES = [
        f"{name}_{phase.lower()}" for phase in PHASENAMES for name in CONSUMPTION_NAMES
    ]

    if mock_envoy.data.system_consumption_phases:
        # if envoy reports consumption these should be defined and have data
        CONSUMPTION_PHASE_TARGET = list(
            itertools.chain(
                *[
                    (
                        phase_data.watts_now / 1000.0,
                        phase_data.watt_hours_today / 1000.0,
                        phase_data.watt_hours_last_7_days / 1000.0,
                        phase_data.watt_hours_lifetime / 1000000.0,
                    )
                    for phase, phase_data in mock_envoy.data.system_consumption_phases.items()
                ]
            )
        )

        for name, target in zip(CONSUMPTION_PHASE_NAMES, CONSUMPTION_PHASE_TARGET):
            assert target == float(hass.states.get(f"{entity_base}_{name}").state)

    if not mock_envoy.data.system_consumption_phases:
        # if no consumptionphase data test they don't exist
        for name in CONSUMPTION_PHASE_NAMES:
            assert f"{entity_base}_{name}" not in entity_status


@pytest.mark.parametrize(("mock_envoy"), *ALL_FIXTURES, indirect=["mock_envoy"])
async def test_grid_data(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_envoy: AsyncMock,
    entity_registry: AsyncMock,
    serial_number,
) -> None:
    """Test enphase_envoy grid entities values and names."""
    await setup_with_selected_platforms(hass, config_entry, [Platform.SENSOR])
    assert entity_registry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    if len(entity_entries) == 0:
        # no entities to test with, other tests test this
        return

    entity_status = {}
    for entity_entry in entity_entries:
        entity_status[entity_entry.entity_id] = entity_entry.disabled_by

    entity_base = f"{Platform.SENSOR}.envoy_{serial_number}"

    CT_CONSUMPTION_NAMES = (
        "lifetime_net_energy_consumption",
        "lifetime_net_energy_production",
        "current_net_power_consumption",
    )
    CT_CONSUMPTION_NAMES_DISABLED = (
        "frequency_net_consumption_ct",
        "voltage_net_consumption_ct",
        "metering_status_net_consumption_ct",
        "meter_status_flags_active_net_consumption_ct",
    )

    if mock_envoy.data.ctmeter_consumption:
        # these should be defined and have value from data
        data = mock_envoy.data.ctmeter_consumption
        CT_CONSUMPTION_TARGETS = (
            data.energy_delivered / 1000000.0,
            data.energy_received / 1000000.0,
            data.active_power / 1000.0,
        )
        for name, target in zip(CT_CONSUMPTION_NAMES, CT_CONSUMPTION_TARGETS):
            assert target == float(hass.states.get(f"{entity_base}_{name}").state)

        # these should be disabled by default
        for name in CT_CONSUMPTION_NAMES_DISABLED:
            assert entity_status[f"{entity_base}_{name}"]

    CT_PRODUCTION_NAMES_DISABLED = (
        "metering_status_production_ct",
        "meter_status_flags_active_production_ct",
    )
    if mock_envoy.data.ctmeter_production:
        # these should be disabled by default
        for name in CT_PRODUCTION_NAMES_DISABLED:
            assert entity_status[f"{entity_base}_{name}"]

    CT_CONSUMPTION_PHASE_NAMES = [
        f"{name}_{phase.lower()}"
        for phase in PHASENAMES
        for name in (CT_CONSUMPTION_NAMES + CT_CONSUMPTION_NAMES_DISABLED)
    ]

    if mock_envoy.data.ctmeter_consumption_phases:
        # these should be disabled by default
        for name in CT_CONSUMPTION_PHASE_NAMES:
            assert entity_status[f"{entity_base}_{name}"]

    CT_PRODUCTION_PHASE_NAMES = [
        f"{name}_{phase.lower()}"
        for phase in PHASENAMES
        for name in CT_PRODUCTION_NAMES_DISABLED
    ]

    if mock_envoy.data.ctmeter_production_phases:
        # these should be disabled by default
        for name in CT_PRODUCTION_PHASE_NAMES:
            assert entity_status[f"{entity_base}_{name}"]

    if not mock_envoy.data.ctmeter_consumption:
        # these should not be defined if no ct meter
        for name in CT_CONSUMPTION_NAMES + CT_CONSUMPTION_NAMES_DISABLED:
            assert f"{entity_base}_{name}" not in entity_status

    if not mock_envoy.data.ctmeter_production:
        # these should not be defined if no ctmeter
        for name in CT_PRODUCTION_NAMES_DISABLED:
            assert f"{entity_base}_{name}" not in entity_status

    if not mock_envoy.data.ctmeter_consumption_phases:
        # these should not be defined if no ct meter phase
        for name in CT_CONSUMPTION_PHASE_NAMES:
            assert f"{entity_base}_{name}" not in entity_status

    if not mock_envoy.data.ctmeter_production_phases:
        # these should not be defined if no ct meter phase
        for name in CT_PRODUCTION_PHASE_NAMES:
            assert f"{entity_base}_{name}" not in entity_status


@pytest.mark.parametrize(("mock_envoy"), *ALL_FIXTURES, indirect=["mock_envoy"])
async def test_battery_storage_data(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_envoy: AsyncMock,
    entity_registry: AsyncMock,
    serial_number,
) -> None:
    """Test enphase_envoy battery storage ct entities values and names."""
    await setup_with_selected_platforms(hass, config_entry, [Platform.SENSOR])
    assert entity_registry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    if len(entity_entries) == 0:
        # no entities to test with, other tests test this
        return

    entity_status = {}
    for entity_entry in entity_entries:
        entity_status[entity_entry.entity_id] = entity_entry.disabled_by

    entity_base = f"{Platform.SENSOR}.envoy_{serial_number}"

    CT_STORAGE_NAMES = (
        "lifetime_battery_energy_discharged",
        "lifetime_battery_energy_charged",
        "current_battery_discharge",
    )
    CT_STORAGE_NAMES_DISABLED = (
        "voltage_storage_ct",
        "metering_status_storage_ct",
        "meter_status_flags_active_storage_ct",
    )

    if mock_envoy.data.ctmeter_storage:
        # these should be defined and have value from data
        data = mock_envoy.data.ctmeter_storage
        CT_STORAGE_TARGETS = (
            data.energy_delivered / 1000000.0,
            data.energy_received / 1000000.0,
            data.active_power / 1000.0,
        )
        for name, target in zip(CT_STORAGE_NAMES, CT_STORAGE_TARGETS):
            assert target == float(hass.states.get(f"{entity_base}_{name}").state)

        # these should be disabled by default
        for name in CT_STORAGE_NAMES_DISABLED:
            assert entity_status[f"{entity_base}_{name}"]

    CT_STORAGE_PHASE_NAMES = [
        f"{name}_{phase.lower()}"
        for phase in PHASENAMES
        for name in (CT_STORAGE_NAMES + CT_STORAGE_NAMES_DISABLED)
    ]

    if mock_envoy.data.ctmeter_storage_phases:
        # these should be disabled by default
        for name in CT_STORAGE_PHASE_NAMES:
            assert entity_status[f"{entity_base}_{name}"]

    if not mock_envoy.data.ctmeter_storage:
        # these should not be created
        for name in CT_STORAGE_NAMES:
            assert f"{entity_base}_{name}" not in entity_status

    if not mock_envoy.data.ctmeter_storage_phases:
        # these should not be created
        for name in CT_STORAGE_PHASE_NAMES:
            assert f"{entity_base}_{name}" not in entity_status


@pytest.mark.parametrize(("mock_envoy"), *ALL_FIXTURES, indirect=["mock_envoy"])
async def test_sensor_inverter_data(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_envoy: AsyncMock,
    entity_registry: AsyncMock,
    serial_number,
) -> None:
    """Test enphase_envoy inverter entities values and names."""
    await setup_with_selected_platforms(hass, config_entry, [Platform.SENSOR])
    assert entity_registry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    if len(entity_entries) == 0:
        # no entities to test with, other tests test this
        return

    entity_status = {}
    for entity_entry in entity_entries:
        entity_status[entity_entry.entity_id] = entity_entry.disabled_by

    entity_base = f"{Platform.SENSOR}.inverter"

    for sn, inverter in mock_envoy.data.inverters.items():
        # these should be created and match data
        assert (inverter.last_report_watts) == float(
            hass.states.get(f"{entity_base}_{sn}").state
        )
        # last reported should be disabled
        assert entity_status[f"{entity_base}_{sn}_last_reported"]


@pytest.mark.parametrize(("mock_envoy"), *ALL_FIXTURES, indirect=["mock_envoy"])
async def test_sensor_encharge_aggregate_data(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_envoy: AsyncMock,
    entity_registry: AsyncMock,
    serial_number,
) -> None:
    """Test enphase_envoy encharge aggregate entities values and names."""
    await setup_with_selected_platforms(hass, config_entry, [Platform.SENSOR])
    assert entity_registry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    if len(entity_entries) == 0:
        # no entities to test with, other tests test this
        return

    entity_status = {}
    for entity_entry in entity_entries:
        entity_status[entity_entry.entity_id] = entity_entry.disabled_by

    entity_base = f"{Platform.SENSOR}.envoy_{serial_number}"

    ENCHARGE_NAMES = (
        "battery",
        "reserve_battery_level",
        "available_battery_energy",
        "reserve_battery_energy",
        "battery_capacity",
    )

    if mock_envoy.data.encharge_aggregate:
        # these should be defined and have value from data
        data = mock_envoy.data.encharge_aggregate
        ENCHARGE_TARGETS = (
            data.state_of_charge,
            data.reserve_state_of_charge,
            data.available_energy,
            data.backup_reserve,
            data.max_available_capacity,
        )
        for name, target in zip(ENCHARGE_NAMES, ENCHARGE_TARGETS):
            assert target == float(hass.states.get(f"{entity_base}_{name}").state)

    if not mock_envoy.data.encharge_aggregate:
        # these should not be created
        for name in ENCHARGE_NAMES:
            assert f"{entity_base}_{name}" not in entity_status


@pytest.mark.parametrize(("mock_envoy"), *ALL_FIXTURES, indirect=["mock_envoy"])
async def test_sensor_encharge_enpower_data(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_envoy: AsyncMock,
    entity_registry: AsyncMock,
) -> None:
    """Test enphase_envoy enpower entities values and names."""
    await setup_with_selected_platforms(hass, config_entry, [Platform.SENSOR])
    assert entity_registry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    assert entity_entries
    if len(entity_entries) == 0:
        # no entities to test with, other tests test this
        return

    entity_status = {}
    for entity_entry in entity_entries:
        entity_status[entity_entry.entity_id] = entity_entry.disabled_by

    entity_base = f"{Platform.SENSOR}.enpower_"

    if mock_envoy.data.enpower:
        # these should be defined and have value from data
        sn = mock_envoy.data.enpower.serial_number
        if mock_envoy.data.enpower.temperature_unit == "F":
            assert mock_envoy.data.enpower.temperature == round(
                TemperatureConverter.convert(
                    float(hass.states.get(f"{entity_base}{sn}_temperature").state),
                    hass.config.units.temperature_unit,
                    UnitOfTemperature.FAHRENHEIT,
                )
            )
        else:
            assert mock_envoy.data.enpower.temperature == round(
                TemperatureConverter.convert(
                    float(hass.states.get(f"{entity_base}{sn}_temperature").state),
                    hass.config.units.temperature_unit,
                    UnitOfTemperature.CELSIUS,
                )
            )
        assert dt_util.utc_from_timestamp(
            mock_envoy.data.enpower.last_report_date
        ) == dt_util.parse_datetime(
            hass.states.get(f"{entity_base}{sn}_last_reported").state
        )


@pytest.mark.parametrize(("mock_envoy"), *ALL_FIXTURES, indirect=["mock_envoy"])
async def test_sensor_encharge_power_data(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_envoy: AsyncMock,
    entity_registry: AsyncMock,
) -> None:
    """Test enphase_envoy encharge_power entities values and names."""
    await setup_with_selected_platforms(hass, config_entry, [Platform.SENSOR])
    assert entity_registry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    if len(entity_entries) == 0:
        # no entities to test with, other tests test this
        return

    entity_status = {}
    for entity_entry in entity_entries:
        entity_status[entity_entry.entity_id] = entity_entry.disabled_by

    entity_base = f"{Platform.SENSOR}.encharge_"

    ENCHARGE_NAMES = (
        "battery",
        "apparent_power",
        "power",
    )

    if mock_envoy.data.encharge_power:
        # these should be defined and have value from data
        ENCHARGE_TARGETS = [
            (
                sn,
                (
                    encharge_power.soc,
                    encharge_power.apparent_power_mva / 1000.0,
                    encharge_power.real_power_mw / 1000.0,
                ),
            )
            for sn, encharge_power in mock_envoy.data.encharge_power.items()
        ]

        for sn, sn_target in ENCHARGE_TARGETS:
            for name, target in zip(ENCHARGE_NAMES, sn_target):
                assert target == float(
                    hass.states.get(f"{entity_base}{sn}_{name}").state
                )

    if mock_envoy.data.encharge_inventory:
        # these should be defined and have value from data
        for sn, encharge_inventory in mock_envoy.data.encharge_inventory.items():
            if encharge_inventory.temperature_unit == "F":
                assert encharge_inventory.temperature == round(
                    TemperatureConverter.convert(
                        float(hass.states.get(f"{entity_base}{sn}_temperature").state),
                        hass.config.units.temperature_unit,
                        UnitOfTemperature.FAHRENHEIT,
                    )
                )
            else:
                assert encharge_inventory.temperature == round(
                    TemperatureConverter.convert(
                        float(hass.states.get(f"{entity_base}{sn}_temperature").state),
                        hass.config.units.temperature_unit,
                        UnitOfTemperature.CELSIUS,
                    )
                )
            assert dt_util.utc_from_timestamp(
                encharge_inventory.last_report_date
            ) == dt_util.parse_datetime(
                hass.states.get(f"{entity_base}{sn}_last_reported").state
            )
