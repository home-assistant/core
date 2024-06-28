"""Test Enphase Envoy sensors."""

from collections.abc import AsyncGenerator
import itertools
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from pyenphase import Envoy, EnvoyTokenAuth
from pyenphase.const import PHASENAMES
from pyenphase.models.meters import CtType
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy import DOMAIN
from homeassistant.components.enphase_envoy.const import Platform
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import TemperatureConverter

from . import load_envoy_fixture

from tests.common import MockConfigEntry

SENSOR_FIXTURES = (
    [
        pytest.param("envoy", 5, 6, id="envoy"),
        pytest.param(
            "envoy_metered_batt_relay", 27, 106, id="envoy_metered_batt_relay"
        ),
        pytest.param("envoy_nobatt_metered_3p", 12, 70, id="envoy_nobatt_metered_3p"),
        pytest.param("envoy_1p_metered", 12, 19, id="envoy_1p_metered"),
        pytest.param("envoy_tot_cons_metered", 5, 8, id="envoy_tot_cons_metered"),
    ],
)


@pytest.fixture(name="setup_enphase_envoy_sensor")
async def setup_enphase_envoy_sensor_fixture(
    hass: HomeAssistant, config: dict[str, str], sensor_envoy: AsyncMock
) -> AsyncGenerator[None, None]:
    """Define a fixture to set up Enphase Envoy with sensor platform only."""
    with (
        patch(
            "homeassistant.components.enphase_envoy.config_flow.Envoy",
            return_value=sensor_envoy,
        ),
        patch(
            "homeassistant.components.enphase_envoy.Envoy",
            return_value=sensor_envoy,
        ),
        patch(
            "homeassistant.components.enphase_envoy.PLATFORMS",
            [Platform.SENSOR],
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


@pytest.mark.parametrize(
    ("sensor_envoy", "entity_count", "enabled_entity_count"),
    *SENSOR_FIXTURES,
    indirect=["sensor_envoy"],
)
async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    setup_enphase_envoy_sensor: None,
    sensor_envoy: AsyncMock,
    entity_count: int,
    enabled_entity_count: int,
) -> None:
    """Test enphase_envoy sensor entities."""

    # number entities states should be created from test data
    assert len(hass.states.async_all()) == entity_count

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

    assert len(entity_entries) == enabled_entity_count

    # compare registered entities against snapshot of prior run
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert hass.states.get(entity_entry.entity_id) == snapshot(
            name=f"{entity_entry.entity_id}-state"
        )


@pytest.mark.parametrize(
    ("sensor_envoy", "entity_count", "enabled_entity_count"),
    *SENSOR_FIXTURES,
    indirect=["sensor_envoy"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_enabled_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    sensor_envoy: AsyncMock,
    setup_enphase_envoy_sensor: None,
    entity_registry: er.EntityRegistry,
    entity_count: int,
    enabled_entity_count: int,
) -> None:
    """Test enphase_envoy sensor entities."""

    # number entities states should be created from test data
    assert len(hass.states.async_all()) == enabled_entity_count

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

    assert len(entity_entries) == enabled_entity_count

    # compare registered entities against snapshot of prior run
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert hass.states.get(entity_entry.entity_id) == snapshot(
            name=f"{entity_entry.entity_id}-state"
        )


@pytest.mark.parametrize(
    ("sensor_envoy", "entity_count", "enabled_entity_count"),
    *SENSOR_FIXTURES,
    indirect=["sensor_envoy"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_production_consumption_data(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    sensor_envoy: AsyncMock,
    setup_enphase_envoy_sensor: None,
    entity_registry: er.EntityRegistry,
    serial_number: str,
    entity_count: int,
    enabled_entity_count: int,
) -> None:
    """Test enphase_envoy production entities values and names."""

    assert len(hass.states.async_all()) == enabled_entity_count

    assert entity_registry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

    entity_status = {}
    for entity_entry in entity_entries:
        entity_status[entity_entry.entity_id] = entity_entry.disabled_by

    entity_base = f"{Platform.SENSOR}.envoy_{serial_number}"

    PRODUCTION_NAMES: Any = (
        "current_power_production",
        "energy_production_today",
        "energy_production_last_seven_days",
        "lifetime_energy_production",
    )
    data = sensor_envoy.data.system_production
    PRODUCTION_TARGETS: Any = (
        data.watts_now / 1000.0,
        data.watt_hours_today / 1000.0,
        data.watt_hours_last_7_days / 1000.0,
        data.watt_hours_lifetime / 1000000.0,
    )

    # production sensors is bare minimum and should be defined
    for name, target in list(zip(PRODUCTION_NAMES, PRODUCTION_TARGETS, strict=False)):
        assert (entity_state := hass.states.get(f"{entity_base}_{name}"))
        assert target == float(entity_state.state)

    CONSUMPTION_NAMES = (
        "current_power_consumption",
        "energy_consumption_today",
        "energy_consumption_last_seven_days",
        "lifetime_energy_consumption",
    )

    if sensor_envoy.data.system_consumption:
        # if consumption is available these should be defined
        data = sensor_envoy.data.system_consumption
        CONSUMPTION_TARGETS = (
            data.watts_now / 1000.0,
            data.watt_hours_today / 1000.0,
            data.watt_hours_last_7_days / 1000.0,
            data.watt_hours_lifetime / 1000000.0,
        )
        for name, target in list(
            zip(CONSUMPTION_NAMES, CONSUMPTION_TARGETS, strict=False)
        ):
            assert (entity_state := hass.states.get(f"{entity_base}_{name}"))
            assert target == float(entity_state.state)

    if not sensor_envoy.data.system_consumption:
        # these should not be defined if no consumption is reported
        for name in CONSUMPTION_NAMES:
            assert f"{entity_base}_{name}" not in entity_status

    PRODUCTION_PHASE_NAMES: Any = [
        f"{name}_{phase.lower()}" for phase in PHASENAMES for name in PRODUCTION_NAMES
    ]

    if sensor_envoy.data.system_production_phases:
        PRODUCTION_PHASE_TARGET = list(
            itertools.chain(
                *[
                    (
                        phase_data.watts_now / 1000.0,
                        phase_data.watt_hours_today / 1000.0,
                        phase_data.watt_hours_last_7_days / 1000.0,
                        phase_data.watt_hours_lifetime / 1000000.0,
                    )
                    for phase_data in sensor_envoy.data.system_production_phases.values()
                ]
            )
        )

        for name, target in list(
            zip(PRODUCTION_PHASE_NAMES, PRODUCTION_PHASE_TARGET, strict=False)
        ):
            assert (entity_state := hass.states.get(f"{entity_base}_{name}"))
            assert target == float(entity_state.state)

    if not sensor_envoy.data.system_production_phases:
        # these should not be defined if no phase data is reported
        for name in PRODUCTION_PHASE_NAMES:
            assert f"{entity_base}_{name}" not in entity_status

    CONSUMPTION_PHASE_NAMES = [
        f"{name}_{phase.lower()}" for phase in PHASENAMES for name in CONSUMPTION_NAMES
    ]

    if sensor_envoy.data.system_consumption_phases:
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
                    for phase_data in sensor_envoy.data.system_consumption_phases.values()
                ]
            )
        )

        for name, target in list(
            zip(CONSUMPTION_PHASE_NAMES, CONSUMPTION_PHASE_TARGET, strict=False)
        ):
            assert (entity_state := hass.states.get(f"{entity_base}_{name}"))
            assert target == float(entity_state.state)

    if not sensor_envoy.data.system_consumption_phases:
        # if no consumptionphase data test they don't exist
        for name in CONSUMPTION_PHASE_NAMES:
            assert f"{entity_base}_{name}" not in entity_status


@pytest.mark.parametrize(
    ("sensor_envoy", "entity_count", "enabled_entity_count"),
    *SENSOR_FIXTURES,
    indirect=["sensor_envoy"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_grid_data(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    sensor_envoy: AsyncMock,
    setup_enphase_envoy_sensor: None,
    entity_registry: er.EntityRegistry,
    serial_number: str,
    entity_count: int,
    enabled_entity_count: int,
) -> None:
    """Test enphase_envoy grid entities values and names."""

    assert len(hass.states.async_all()) == enabled_entity_count

    assert entity_registry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

    entity_status = {}
    for entity_entry in entity_entries:
        entity_status[entity_entry.entity_id] = entity_entry.disabled_by

    entity_base = f"{Platform.SENSOR}.envoy_{serial_number}"

    CT_CONSUMPTION_NAMES_FLOAT = (
        "lifetime_net_energy_consumption",
        "lifetime_net_energy_production",
        "current_net_power_consumption",
        "frequency_net_consumption_ct",
        "voltage_net_consumption_ct",
        "meter_status_flags_active_net_consumption_ct",
    )
    CT_CONSUMPTION_NAMES_STR = ("metering_status_net_consumption_ct",)

    if sensor_envoy.data.ctmeter_consumption and (
        sensor_envoy.consumption_meter_type == CtType.NET_CONSUMPTION
    ):
        # if consumption meter data, entities should be created and have values
        data = sensor_envoy.data.ctmeter_consumption

        CT_CONSUMPTION_TARGETS_FLOAT = (
            data.energy_delivered / 1000000.0,
            data.energy_received / 1000000.0,
            data.active_power / 1000.0,
            data.frequency,
            data.voltage,
            len(data.status_flags),
        )
        for name, target in list(
            zip(CT_CONSUMPTION_NAMES_FLOAT, CT_CONSUMPTION_TARGETS_FLOAT, strict=False)
        ):
            assert (entity_state := hass.states.get(f"{entity_base}_{name}"))
            assert target == float(entity_state.state)

        CT_CONSUMPTION_TARGETS_STR = (data.metering_status,)
        for name, target in list(
            zip(CT_CONSUMPTION_NAMES_STR, CT_CONSUMPTION_TARGETS_STR, strict=False)
        ):
            assert (entity_state := hass.states.get(f"{entity_base}_{name}"))
            assert target == entity_state.state

    CT_PRODUCTION_NAMES_FLOAT = ("meter_status_flags_active_production_ct",)
    CT_PRODUCTION_NAMES_STR = ("metering_status_production_ct",)

    if sensor_envoy.data.ctmeter_production and (
        sensor_envoy.production_meter_type == CtType.PRODUCTION
    ):
        # if production meter data, entities should be created and have values
        data = sensor_envoy.data.ctmeter_production

        CT_PRODUCTION_TARGETS_FLOAT = (len(data.status_flags),)
        for name, target in list(
            zip(CT_PRODUCTION_NAMES_FLOAT, CT_PRODUCTION_TARGETS_FLOAT, strict=False)
        ):
            assert (entity_state := hass.states.get(f"{entity_base}_{name}"))
            assert target == float(entity_state.state)

        CT_PRODUCTION_TARGETS_STR = (data.metering_status,)
        for name, target in list(
            zip(CT_PRODUCTION_NAMES_STR, CT_PRODUCTION_TARGETS_STR, strict=False)
        ):
            assert (entity_state := hass.states.get(f"{entity_base}_{name}"))
            assert target == entity_state.state

    CT_CONSUMPTION_NAMES_FLOAT_PHASE = [
        f"{name}_{phase.lower()}"
        for phase in PHASENAMES
        for name in CT_CONSUMPTION_NAMES_FLOAT
    ]

    CT_CONSUMPTION_NAMES_STR_PHASE = [
        f"{name}_{phase.lower()}"
        for phase in PHASENAMES
        for name in CT_CONSUMPTION_NAMES_STR
    ]

    if sensor_envoy.data.ctmeter_consumption_phases and (
        sensor_envoy.consumption_meter_type == CtType.NET_CONSUMPTION
    ):
        # if consumption meter phase data, entities should be created and have values
        CT_CONSUMPTION_NAMES_FLOAT_PHASE_TARGET = list(
            itertools.chain(
                *[
                    (
                        phase_data.energy_delivered / 1000000.0,
                        phase_data.energy_received / 1000000.0,
                        phase_data.active_power / 1000.0,
                        phase_data.frequency,
                        phase_data.voltage,
                        len(phase_data.status_flags),
                    )
                    for phase_data in sensor_envoy.data.ctmeter_consumption_phases.values()
                ]
            )
        )
        for name, target in list(
            zip(
                CT_CONSUMPTION_NAMES_FLOAT_PHASE,
                CT_CONSUMPTION_NAMES_FLOAT_PHASE_TARGET,
                strict=False,
            )
        ):
            assert (entity_state := hass.states.get(f"{entity_base}_{name}"))
            assert target == float(entity_state.state)

        CT_CONSUMPTION_NAMES_STR_PHASE_TARGET = list(
            itertools.chain(
                *[
                    (phase_data.metering_status,)
                    for phase_data in sensor_envoy.data.ctmeter_consumption_phases.values()
                ]
            )
        )

        for name, target in list(
            zip(
                CT_CONSUMPTION_NAMES_STR_PHASE,
                CT_CONSUMPTION_NAMES_STR_PHASE_TARGET,
                strict=False,
            )
        ):
            assert (entity_state := hass.states.get(f"{entity_base}_{name}"))
            assert target == entity_state.state

    CT_PRODUCTION_NAMES_FLOAT_PHASE = [
        f"{name}_{phase.lower()}"
        for phase in PHASENAMES
        for name in CT_PRODUCTION_NAMES_FLOAT
    ]

    CT_PRODUCTION_NAMES_STR_PHASE = [
        f"{name}_{phase.lower()}"
        for phase in PHASENAMES
        for name in CT_PRODUCTION_NAMES_STR
    ]

    if sensor_envoy.data.ctmeter_production_phases and (
        sensor_envoy.production_meter_type == CtType.PRODUCTION
    ):
        # if production meter phase data, entities should be created and have values

        CT_PRODUCTION_NAMES_FLOAT_PHASE_TARGET = list(
            itertools.chain(
                *[
                    (len(phase_data.status_flags),)
                    for phase_data in sensor_envoy.data.ctmeter_production_phases.values()
                ]
            )
        )
        for name, target in list(
            zip(
                CT_PRODUCTION_NAMES_FLOAT_PHASE,
                CT_PRODUCTION_NAMES_FLOAT_PHASE_TARGET,
                strict=False,
            )
        ):
            assert (entity_state := hass.states.get(f"{entity_base}_{name}"))
            assert target == float(entity_state.state)

        CT_PRODUCTION_NAMES_STR_PHASE_TARGET = list(
            itertools.chain(
                *[
                    (phase_data.metering_status,)
                    for phase_data in sensor_envoy.data.ctmeter_production_phases.values()
                ]
            )
        )

        for name, target in list(
            zip(
                CT_PRODUCTION_NAMES_STR_PHASE,
                CT_PRODUCTION_NAMES_STR_PHASE_TARGET,
                strict=False,
            )
        ):
            assert (entity_state := hass.states.get(f"{entity_base}_{name}"))
            assert target == entity_state.state

    if (not sensor_envoy.data.ctmeter_consumption) or (
        sensor_envoy.consumption_meter_type != CtType.NET_CONSUMPTION
    ):
        # if no ct consumption meter data or not net meter, no entities should be created
        for name in list(
            zip(CT_CONSUMPTION_NAMES_FLOAT, CT_CONSUMPTION_NAMES_STR, strict=False)
        ):
            assert f"{entity_base}_{name}" not in entity_status

    if not sensor_envoy.data.ctmeter_production:
        # if no ct production meter data, no entities should be created
        for name in list(
            zip(CT_PRODUCTION_NAMES_FLOAT, CT_PRODUCTION_NAMES_STR, strict=False)
        ):
            assert f"{entity_base}_{name}" not in entity_status

    if (not sensor_envoy.data.ctmeter_consumption_phases) or (
        sensor_envoy.consumption_meter_type != CtType.NET_CONSUMPTION
    ):
        # if no ct consumption meter phase data or not net meter, no entities should be created
        for name in list(
            zip(
                CT_CONSUMPTION_NAMES_FLOAT_PHASE,
                CT_CONSUMPTION_NAMES_STR_PHASE,
                strict=False,
            )
        ):
            assert f"{entity_base}_{name}" not in entity_status

    if not sensor_envoy.data.ctmeter_production_phases:
        # if no ct production meter, no entities should be created
        for name in list(
            zip(
                CT_PRODUCTION_NAMES_FLOAT_PHASE,
                CT_PRODUCTION_NAMES_STR_PHASE,
                strict=False,
            )
        ):
            assert f"{entity_base}_{name}" not in entity_status


@pytest.mark.parametrize(
    ("sensor_envoy", "entity_count", "enabled_entity_count"),
    *SENSOR_FIXTURES,
    indirect=["sensor_envoy"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_battery_storage_data(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    sensor_envoy: AsyncMock,
    setup_enphase_envoy_sensor: None,
    entity_registry: er.EntityRegistry,
    serial_number: str,
    entity_count: int,
    enabled_entity_count: int,
) -> None:
    """Test enphase_envoy battery storage ct entities values and names."""

    assert len(hass.states.async_all()) == enabled_entity_count

    assert entity_registry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

    entity_status = {}
    for entity_entry in entity_entries:
        entity_status[entity_entry.entity_id] = entity_entry.disabled_by

    entity_base = f"{Platform.SENSOR}.envoy_{serial_number}"

    CT_STORAGE_NAMES_FLOAT = (
        "lifetime_battery_energy_discharged",
        "lifetime_battery_energy_charged",
        "current_battery_discharge",
        "voltage_storage_ct",
        "meter_status_flags_active_storage_ct",
    )
    CT_STORAGE_NAMES_STR = ("metering_status_storage_ct",)

    if sensor_envoy.data.ctmeter_storage:
        # these should be defined and have value from data
        data = sensor_envoy.data.ctmeter_storage
        CT_STORAGE_TARGETS_FLOAT = (
            data.energy_delivered / 1000000.0,
            data.energy_received / 1000000.0,
            data.active_power / 1000.0,
            data.voltage,
            len(data.status_flags),
        )
        for name, target in list(
            zip(CT_STORAGE_NAMES_FLOAT, CT_STORAGE_TARGETS_FLOAT, strict=False)
        ):
            assert (entity_state := hass.states.get(f"{entity_base}_{name}"))
            assert target == float(entity_state.state)

        CT_STORAGE_TARGETS_STR = (data.metering_status,)
        for name, target in list(
            zip(CT_STORAGE_NAMES_STR, CT_STORAGE_TARGETS_STR, strict=False)
        ):
            assert (entity_state := hass.states.get(f"{entity_base}_{name}"))
            assert target == entity_state.state

    CT_STORAGE_NAMES_FLOAT_PHASE = [
        f"{name}_{phase.lower()}"
        for phase in PHASENAMES
        for name in (CT_STORAGE_NAMES_FLOAT)
    ]

    CT_STORAGE_NAMES_STR_PHASE = [
        f"{name}_{phase.lower()}"
        for phase in PHASENAMES
        for name in (CT_STORAGE_NAMES_STR)
    ]

    if sensor_envoy.data.ctmeter_storage_phases:
        # if storage meter phase data, entities should be created and have values
        CT_STORAGE_NAMES_FLOAT_PHASE_TARGET = list(
            itertools.chain(
                *[
                    (
                        phase_data.energy_delivered / 1000000.0,
                        phase_data.energy_received / 1000000.0,
                        phase_data.active_power / 1000.0,
                        phase_data.voltage,
                        len(phase_data.status_flags),
                    )
                    for phase_data in sensor_envoy.data.ctmeter_storage_phases.values()
                ]
            )
        )
        for name, target in list(
            zip(
                CT_STORAGE_NAMES_FLOAT_PHASE,
                CT_STORAGE_NAMES_FLOAT_PHASE_TARGET,
                strict=False,
            )
        ):
            assert (entity_state := hass.states.get(f"{entity_base}_{name}"))
            assert target == float(entity_state.state)

        CT_STORAGE_NAMES_STR_PHASE_TARGET = list(
            itertools.chain(
                *[
                    (phase_data.metering_status,)
                    for phase_data in sensor_envoy.data.ctmeter_storage_phases.values()
                ]
            )
        )

        for name, target in list(
            zip(
                CT_STORAGE_NAMES_STR_PHASE,
                CT_STORAGE_NAMES_STR_PHASE_TARGET,
                strict=False,
            )
        ):
            assert (entity_state := hass.states.get(f"{entity_base}_{name}"))
            assert target == entity_state.state

    if not sensor_envoy.data.ctmeter_storage:
        # if no storage ct meter  data these should not be created
        for name in list(
            zip(CT_STORAGE_NAMES_FLOAT, CT_STORAGE_NAMES_STR, strict=False)
        ):
            assert f"{entity_base}_{name}" not in entity_status

    if not sensor_envoy.data.ctmeter_storage_phases:
        # if no storage ct meter phase data these should not be created
        for name in list(
            zip(CT_STORAGE_NAMES_FLOAT_PHASE, CT_STORAGE_NAMES_STR_PHASE, strict=False)
        ):
            assert f"{entity_base}_{name}" not in entity_status


@pytest.mark.parametrize(
    ("sensor_envoy", "entity_count", "enabled_entity_count"),
    *SENSOR_FIXTURES,
    indirect=["sensor_envoy"],
)
async def test_sensor_inverter_data(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    sensor_envoy: AsyncMock,
    setup_enphase_envoy_sensor: None,
    entity_registry: er.EntityRegistry,
    serial_number: str,
    entity_count: int,
    enabled_entity_count: int,
) -> None:
    """Test enphase_envoy inverter entities values and names."""

    assert len(hass.states.async_all()) == entity_count

    assert entity_registry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

    entity_status = {}
    for entity_entry in entity_entries:
        entity_status[entity_entry.entity_id] = entity_entry.disabled_by

    entity_base = f"{Platform.SENSOR}.inverter"

    for sn, inverter in sensor_envoy.data.inverters.items():
        # these should be created and match data
        assert (entity_state := hass.states.get(f"{entity_base}_{sn}"))
        assert (inverter.last_report_watts) == float(entity_state.state)
        # last reported should be disabled
        assert entity_status[f"{entity_base}_{sn}_last_reported"]


@pytest.mark.parametrize(
    ("sensor_envoy", "entity_count", "enabled_entity_count"),
    *SENSOR_FIXTURES,
    indirect=["sensor_envoy"],
)
async def test_sensor_encharge_aggregate_data(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    sensor_envoy: AsyncMock,
    setup_enphase_envoy_sensor: None,
    entity_registry: er.EntityRegistry,
    serial_number: str,
    entity_count: int,
    enabled_entity_count: int,
) -> None:
    """Test enphase_envoy encharge aggregate entities values and names."""

    assert len(hass.states.async_all()) == entity_count

    assert entity_registry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

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

    if sensor_envoy.data.encharge_aggregate:
        # these should be defined and have value from data
        data = sensor_envoy.data.encharge_aggregate
        ENCHARGE_TARGETS = (
            data.state_of_charge,
            data.reserve_state_of_charge,
            data.available_energy,
            data.backup_reserve,
            data.max_available_capacity,
        )
        for name, target in list(zip(ENCHARGE_NAMES, ENCHARGE_TARGETS, strict=False)):
            assert (entity_state := hass.states.get(f"{entity_base}_{name}"))
            assert target == float(entity_state.state)

    if not sensor_envoy.data.encharge_aggregate:
        # these should not be created
        for name in ENCHARGE_NAMES:
            assert f"{entity_base}_{name}" not in entity_status


@pytest.mark.parametrize(
    ("sensor_envoy", "entity_count", "enabled_entity_count"),
    *SENSOR_FIXTURES,
    indirect=["sensor_envoy"],
)
async def test_sensor_encharge_enpower_data(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    sensor_envoy: AsyncMock,
    setup_enphase_envoy_sensor: None,
    entity_registry: er.EntityRegistry,
    entity_count: int,
    enabled_entity_count: int,
) -> None:
    """Test enphase_envoy enpower entities values and names."""

    assert entity_registry
    assert len(hass.states.async_all()) == entity_count

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    assert entity_entries

    entity_status = {}
    for entity_entry in entity_entries:
        entity_status[entity_entry.entity_id] = entity_entry.disabled_by

    entity_base = f"{Platform.SENSOR}.enpower_"

    if sensor_envoy.data.enpower:
        # these should be defined and have value from data
        sn = sensor_envoy.data.enpower.serial_number
        if sensor_envoy.data.enpower.temperature_unit == "F":
            assert (entity_state := hass.states.get(f"{entity_base}{sn}_temperature"))
            assert sensor_envoy.data.enpower.temperature == round(
                TemperatureConverter.convert(
                    float(entity_state.state),
                    hass.config.units.temperature_unit,
                    UnitOfTemperature.FAHRENHEIT,
                )
            )
        else:
            assert (entity_state := hass.states.get(f"{entity_base}{sn}_temperature"))
            assert sensor_envoy.data.enpower.temperature == round(
                TemperatureConverter.convert(
                    float(entity_state.state),
                    hass.config.units.temperature_unit,
                    UnitOfTemperature.CELSIUS,
                )
            )
        assert (entity_state := hass.states.get(f"{entity_base}{sn}_last_reported"))
        assert dt_util.utc_from_timestamp(
            sensor_envoy.data.enpower.last_report_date
        ) == dt_util.parse_datetime(entity_state.state)


@pytest.mark.parametrize(
    ("sensor_envoy", "entity_count", "enabled_entity_count"),
    *SENSOR_FIXTURES,
    indirect=["sensor_envoy"],
)
async def test_sensor_encharge_power_data(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    sensor_envoy: AsyncMock,
    setup_enphase_envoy_sensor: None,
    entity_registry: er.EntityRegistry,
    entity_count: int,
    enabled_entity_count: int,
) -> None:
    """Test enphase_envoy encharge_power entities values and names."""

    assert len(hass.states.async_all()) == entity_count

    assert entity_registry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

    entity_status = {}
    for entity_entry in entity_entries:
        entity_status[entity_entry.entity_id] = entity_entry.disabled_by

    entity_base = f"{Platform.SENSOR}.encharge_"

    ENCHARGE_NAMES = (
        "battery",
        "apparent_power",
        "power",
    )

    if sensor_envoy.data.encharge_power:
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
            for sn, encharge_power in sensor_envoy.data.encharge_power.items()
        ]

        for sn, sn_target in ENCHARGE_TARGETS:
            for name, target in list(zip(ENCHARGE_NAMES, sn_target, strict=False)):
                assert (entity_state := hass.states.get(f"{entity_base}{sn}_{name}"))
                assert target == float(entity_state.state)

    if sensor_envoy.data.encharge_inventory:
        # these should be defined and have value from data
        for sn, encharge_inventory in sensor_envoy.data.encharge_inventory.items():
            assert (entity_state := hass.states.get(f"{entity_base}{sn}_temperature"))
            assert encharge_inventory.temperature == round(
                TemperatureConverter.convert(
                    float(entity_state.state),
                    hass.config.units.temperature_unit,
                    UnitOfTemperature.FAHRENHEIT
                    if encharge_inventory.temperature_unit == "F"
                    else UnitOfTemperature.CELSIUS,
                )
            )
            assert (entity_state := hass.states.get(f"{entity_base}{sn}_last_reported"))
            assert dt_util.utc_from_timestamp(
                encharge_inventory.last_report_date
            ) == dt_util.parse_datetime(entity_state.state)


@pytest.fixture(name="sensor_envoy")
async def mock_sensor_envoy_fixture(
    serial_number: str,
    mock_authenticate: AsyncMock,
    mock_setup: AsyncMock,
    mock_auth: EnvoyTokenAuth,
    mock_go_on_grid: AsyncMock,
    mock_go_off_grid: AsyncMock,
    mock_open_dry_contact: AsyncMock,
    mock_close_dry_contact: AsyncMock,
    mock_update_dry_contact: AsyncMock,
    mock_disable_charge_from_grid: AsyncMock,
    mock_enable_charge_from_grid: AsyncMock,
    mock_set_reserve_soc: AsyncMock,
    mock_set_storage_mode: AsyncMock,
    request: pytest.FixtureRequest,
) -> AsyncGenerator[AsyncMock, None]:
    """Define a mocked Envoy fixture."""
    mock_envoy = Mock(spec=Envoy)
    with (
        patch(
            "homeassistant.components.enphase_envoy.config_flow.Envoy",
            return_value=mock_envoy,
        ),
        patch(
            "homeassistant.components.enphase_envoy.Envoy",
            return_value=mock_envoy,
        ),
    ):
        # load the fixture
        load_envoy_fixture(mock_envoy, request.param)

        # set the mock for the methods
        mock_envoy.serial_number = serial_number
        mock_envoy.authenticate = mock_authenticate
        mock_envoy.go_off_grid = mock_go_off_grid
        mock_envoy.go_on_grid = mock_go_on_grid
        mock_envoy.open_dry_contact = mock_open_dry_contact
        mock_envoy.close_dry_contact = mock_close_dry_contact
        mock_envoy.disable_charge_from_grid = mock_disable_charge_from_grid
        mock_envoy.enable_charge_from_grid = mock_enable_charge_from_grid
        mock_envoy.update_dry_contact = mock_update_dry_contact
        mock_envoy.set_reserve_soc = mock_set_reserve_soc
        mock_envoy.set_storage_mode = mock_set_storage_mode
        mock_envoy.setup = mock_setup
        mock_envoy.auth = mock_auth
        mock_envoy.update = AsyncMock(return_value=mock_envoy.data)

        return mock_envoy
