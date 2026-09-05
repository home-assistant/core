"""Tests for Victron GX MQTT sensors."""

import logging
import math
from unittest.mock import PropertyMock, patch

import pytest
from victron_mqtt import FormulaMetric, Hub as VictronVenusHub
from victron_mqtt.testing import finalize_injection, inject_message

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.components.victron_gx.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_component import DATA_INSTANCES, EntityComponent

from .const import MOCK_INSTALLATION_ID

from tests.common import MockConfigEntry, mock_restore_cache_with_extra_data

ENERGY_ENTITY_ID = "sensor.victron_venus_pv_energy"


async def test_victron_battery_sensor(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test SENSOR MetricKind - battery current sensor is created and updated."""
    victron_hub, mock_config_entry = init_integration

    # Inject a system metric first so the gateway device (system_0) is registered
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/system/0/SystemState/State",
        '{"value": 1}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    # Verify system device has no via_device (it IS the gateway)
    system_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{MOCK_INSTALLATION_ID}_system_0"), mock_config_entry.entry_id
    )
    assert system_device is not None
    assert system_device.via_device_id is None

    # Inject a sensor metric (battery current)
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/battery/0/Dc/0/Current",
        '{"value": 10.5}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    # Verify entity was created by checking entity registry
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    # Exactly two entities are expected: system state + battery current
    assert len(entities) == 2
    entity = next(e for e in entities if e.entity_id == "sensor.battery_dc_bus_current")
    assert entity.unique_id == f"{MOCK_INSTALLATION_ID}_battery_0_battery_current"
    assert entity.original_device_class is SensorDeviceClass.CURRENT
    assert entity.unit_of_measurement == "A"
    assert entity.translation_key == "battery_current"

    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.state == "10.5"
    assert state.attributes["state_class"] == SensorStateClass.MEASUREMENT
    assert state.attributes["device_class"] == "current"
    assert state.attributes["unit_of_measurement"] == "A"

    # Verify device info was registered correctly
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{MOCK_INSTALLATION_ID}_battery_0"), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.manufacturer == "Victron Energy"
    assert device.name == "Battery"
    # Verify battery device has via_device pointing to system_0 (gateway)
    assert device.via_device_id == system_device.id

    # Update the same metric to exercise the entity update callback path.
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/battery/0/Dc/0/Current",
        '{"value": 11.2}',
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.state == "11.2"


async def test_victron_enum_sensor(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test sensor with VictronEnum value normalizes to enum id."""
    victron_hub, _mock_config_entry = init_integration

    # SystemState/State produces a VictronEnum (State enum)
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/system/0/SystemState/State",
        '{"value": 1}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.victron_venus_system_state")
    assert state is not None
    # Value 1 maps to State.LOW_POWER with id="low_power"
    assert state.state == "low_power"

    # Verify system device has no via_device (it IS the gateway)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{MOCK_INSTALLATION_ID}_system_0"), _mock_config_entry.entry_id
    )
    assert device is not None
    assert device.manufacturer == "Victron Energy"
    assert device.via_device_id is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_victron_main_topic_sensor(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor with main_topic=True keeps translation key and device name."""
    victron_hub, mock_config_entry = init_integration

    # Multi RS MPPT MppOperationMode is a main_topic metric
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/multi/0/Pv/1/MppOperationMode",
        '{"value": 2}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert len(entities) == 1
    entity = entities[0]
    assert entity.unique_id == f"{MOCK_INSTALLATION_ID}_multi_0_multi_mppt_1_state"
    assert entity.translation_key == "multi_mppt_mpptnumber_state"

    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.state == "mppt_active"
    # Entity uses device name only (no separate entity name)
    assert state.attributes["friendly_name"] == "Multi RS Solar"


async def test_native_unit_of_measurement_cost_metric(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
) -> None:
    """Test native_unit_of_measurement returns currency for COST metric type."""
    victron_hub, _mock_config_entry = init_integration

    hass.config.currency = "USD"

    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/evcharger/0/Session/Cost",
        '{"value": 12.34}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.ev_charging_station_last_session_cost")
    assert state is not None
    assert state.attributes["unit_of_measurement"] == "USD"
    assert state.state == "12.34"


async def test_native_unit_of_measurement_with_device_class(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
) -> None:
    """Test native_unit_of_measurement returns unit for metrics with device class."""
    victron_hub, _mock_config_entry = init_integration

    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/battery/0/Dc/0/Current",
        '{"value": 10.5}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.battery_dc_bus_current")
    assert state is not None
    assert state.attributes["unit_of_measurement"] == "A"


async def test_native_unit_of_measurement_special_unit(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
) -> None:
    """Test native_unit_of_measurement returns special units like %."""
    victron_hub, _mock_config_entry = init_integration

    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/battery/0/Soc",
        '{"value": 85}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.battery_charge")
    assert state is not None
    assert state.attributes["unit_of_measurement"] == "%"


async def _inject_pv_power(victron_hub: VictronVenusHub, value: int) -> None:
    """Inject a PV power metric, which drives the pv_energy FormulaMetric."""
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/system/0/Dc/Pv/Power",
        f'{{"value": {value}}}',
    )


def _restore_energy(native_value: object) -> tuple[State, dict[str, object]]:
    """Build a restore-cache entry with a persisted native sensor value."""
    return (
        State(ENERGY_ENTITY_ID, str(native_value)),
        {"native_value": native_value, "native_unit_of_measurement": "kWh"},
    )


async def test_formula_sensor_restores_baseline(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
) -> None:
    """Test cumulative FormulaMetric sensor restores previous value as baseline."""
    victron_hub, _mock_config_entry = init_integration

    mock_restore_cache_with_extra_data(hass, (_restore_energy(5.0),))

    await _inject_pv_power(victron_hub, 100)
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    state = hass.states.get(ENERGY_ENTITY_ID)
    assert state is not None
    assert state.attributes["state_class"] == SensorStateClass.TOTAL
    # Fresh formula value is 0.0, restored baseline of 5.0 is added on top.
    assert state.state == "5.0"

    # A new reading of 10.0 is accumulated on top of the restored baseline.
    with patch.object(
        FormulaMetric, "value", new_callable=PropertyMock, return_value=10.0
    ):
        await _inject_pv_power(victron_hub, 200)
        await hass.async_block_till_done()

    state = hass.states.get(ENERGY_ENTITY_ID)
    assert state is not None
    assert state.state == "15.0"


async def test_formula_sensor_none_update_after_restore(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
) -> None:
    """Test a None update marks the sensor unavailable but keeps its value."""
    victron_hub, _mock_config_entry = init_integration

    mock_restore_cache_with_extra_data(hass, (_restore_energy(5.0),))

    await _inject_pv_power(victron_hub, 100)
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    state = hass.states.get(ENERGY_ENTITY_ID)
    assert state is not None
    assert state.state == "5.0"

    # A None update (stale/unavailable dependency) marks the entity unavailable
    # while keeping the last known value, so the restored total is not persisted
    # as None and lost on the next restart.
    with patch.object(
        FormulaMetric, "value", new_callable=PropertyMock, return_value=None
    ):
        await _inject_pv_power(victron_hub, 200)
        await hass.async_block_till_done()

    state = hass.states.get(ENERGY_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # The last known value is retained on the entity, so RestoreSensor persists
    # the accumulated total instead of None.
    component: EntityComponent[SensorEntity] = hass.data[DATA_INSTANCES][SENSOR_DOMAIN]
    entity = component.get_entity(ENERGY_ENTITY_ID)
    assert entity is not None
    assert entity.native_value == 5.0


@pytest.mark.parametrize(
    ("restore_cache", "expected_log"),
    [
        pytest.param((), "Baseline is missing", id="first_load"),
        pytest.param(
            (_restore_energy(None),),
            "Baseline is missing",
            id="missing_native_value",
        ),
        pytest.param(
            (_restore_energy("not_a_number"),),
            "Could not restore state",
            id="invalid_native_value",
        ),
        pytest.param(
            (_restore_energy(math.nan),),
            "Could not restore state",
            id="nan_native_value",
        ),
        pytest.param(
            (_restore_energy(math.inf),),
            "Could not restore state",
            id="inf_native_value",
        ),
    ],
)
async def test_formula_sensor_no_baseline(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    caplog: pytest.LogCaptureFixture,
    restore_cache: tuple[tuple[State, dict[str, object]], ...],
    expected_log: str,
) -> None:
    """Test FormulaMetric sensor keeps fresh value when no valid baseline exists."""
    victron_hub, _mock_config_entry = init_integration

    mock_restore_cache_with_extra_data(hass, restore_cache)

    with caplog.at_level(logging.DEBUG, logger="homeassistant.components.victron_gx"):
        await _inject_pv_power(victron_hub, 100)
        await finalize_injection(victron_hub)
        await hass.async_block_till_done()

    state = hass.states.get(ENERGY_ENTITY_ID)
    assert state is not None
    assert state.state == "0.0"
    assert expected_log in caplog.text


async def test_formula_sensor_non_numeric_value(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test FormulaMetric sensor with non-numeric value does not restore baseline."""
    victron_hub, _mock_config_entry = init_integration

    mock_restore_cache_with_extra_data(hass, (_restore_energy(5.0),))

    with (
        patch.object(
            FormulaMetric, "value", new_callable=PropertyMock, return_value=None
        ),
        caplog.at_level(logging.WARNING, logger="homeassistant.components.victron_gx"),
    ):
        await _inject_pv_power(victron_hub, 100)
        await finalize_injection(victron_hub)
        await hass.async_block_till_done()

    state = hass.states.get(ENERGY_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert "Cannot restore baseline" in caplog.text
