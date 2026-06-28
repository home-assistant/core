"""Test Subaru sensors."""

import copy
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.subaru.const import DOMAIN, VEHICLE_STATUS
from homeassistant.components.subaru.sensor import (
    API_GEN_2_SENSORS,
    EV_SENSORS,
    SAFETY_SENSORS,
)
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .api_responses import (
    EXPECTED_STATE_EV_METRIC,
    EXPECTED_STATE_EV_UNAVAILABLE,
    TEST_VIN_2_EV,
    VEHICLE_STATUS_EV,
)
from .conftest import (
    MOCK_API_FETCH,
    MOCK_API_GET_DATA,
    advance_time_to_next_fetch,
    setup_subaru_config_entry,
)

from tests.common import MockConfigEntry, get_sensor_display_state


async def test_sensors_ev_metric(hass: HomeAssistant, ev_entry) -> None:
    """Test sensors supporting metric units."""
    _assert_data(hass, EXPECTED_STATE_EV_METRIC)


async def test_sensors_missing_vin_data(hass: HomeAssistant, ev_entry) -> None:
    """Test for missing VIN dataset."""
    with patch(MOCK_API_FETCH), patch(MOCK_API_GET_DATA, return_value=None):
        advance_time_to_next_fetch(hass)
        await hass.async_block_till_done()

    _assert_data(hass, EXPECTED_STATE_EV_UNAVAILABLE)


@pytest.mark.parametrize(
    ("entitydata", "old_unique_id", "new_unique_id"),
    [
        (
            {
                "domain": SENSOR_DOMAIN,
                "platform": DOMAIN,
                "unique_id": f"{TEST_VIN_2_EV}_Avg fuel consumption",
            },
            f"{TEST_VIN_2_EV}_Avg fuel consumption",
            f"{TEST_VIN_2_EV}_{API_GEN_2_SENSORS[0].key}",
        ),
    ],
)
async def test_sensor_migrate_unique_ids(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entitydata,
    old_unique_id,
    new_unique_id,
    subaru_config_entry,
) -> None:
    """Test successful migration of entity unique_ids."""
    entity: er.RegistryEntry = entity_registry.async_get_or_create(
        **entitydata,
        config_entry=subaru_config_entry,
    )
    assert entity.unique_id == old_unique_id

    await setup_subaru_config_entry(hass, subaru_config_entry)

    entity_migrated = entity_registry.async_get(entity.entity_id)
    assert entity_migrated
    assert entity_migrated.unique_id == new_unique_id


@pytest.mark.parametrize(
    ("entitydata", "old_unique_id", "new_unique_id"),
    [
        (
            {
                "domain": SENSOR_DOMAIN,
                "platform": DOMAIN,
                "unique_id": f"{TEST_VIN_2_EV}_Avg fuel consumption",
            },
            f"{TEST_VIN_2_EV}_Avg fuel consumption",
            f"{TEST_VIN_2_EV}_{API_GEN_2_SENSORS[0].key}",
        )
    ],
)
async def test_sensor_migrate_unique_ids_duplicate(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entitydata,
    old_unique_id,
    new_unique_id,
    subaru_config_entry,
) -> None:
    """Test unsuccessful migration of entity unique_ids due to duplicate."""
    entity: er.RegistryEntry = entity_registry.async_get_or_create(
        **entitydata,
        config_entry=subaru_config_entry,
    )
    assert entity.unique_id == old_unique_id

    # create existing entry with new_unique_id that conflicts with migrate
    existing_entity = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        unique_id=new_unique_id,
        config_entry=subaru_config_entry,
    )

    await setup_subaru_config_entry(hass, subaru_config_entry)

    entity_migrated = entity_registry.async_get(entity.entity_id)
    assert entity_migrated
    assert entity_migrated.unique_id == old_unique_id

    entity_not_changed = entity_registry.async_get(existing_entity.entity_id)
    assert entity_not_changed
    assert entity_not_changed.unique_id == new_unique_id

    assert entity_migrated != entity_not_changed


def _assert_data(hass: HomeAssistant, expected_state: dict[str, Any]) -> None:
    sensor_list = EV_SENSORS
    sensor_list.extend(API_GEN_2_SENSORS)
    sensor_list.extend(SAFETY_SENSORS)
    expected_states = {}
    entity_registry = er.async_get(hass)
    for item in sensor_list:
        # Disabled-by-default sensors (e.g. the *_raw diagnostic companions)
        # aren't loaded into the state machine, so there's nothing to assert.
        if not item.entity_registry_enabled_default:
            continue
        entity = entity_registry.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, f"{TEST_VIN_2_EV}_{item.key}"
        )
        expected_states[entity] = expected_state[item.key]

    for sensor, value in expected_states.items():
        state = get_sensor_display_state(hass, entity_registry, sensor)
        assert state == value


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "ev_entry")
async def test_recommended_tire_pressure_from_vehicle_health(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Recommended tire pressure sensors derive their value from vehicle_health.

    These sensors are disabled-by-default diagnostics, so they're skipped in
    `_assert_data`. Enable them here to exercise the `value_fn`-from-
    `vehicle_health` path (the only consumer of nested-section value_fn in
    the integration today). Fixture has FRONT_TIRES=35 / REAR_TIRES=33 PSI;
    the test default unit system is metric, so HA's pressure conversion
    surfaces them as kPa.
    """
    front = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{TEST_VIN_2_EV}_recommended_tire_pressure_front"
    )
    assert front is not None
    assert (
        get_sensor_display_state(hass, entity_registry, front)
        == EXPECTED_STATE_EV_METRIC["recommended_tire_pressure_front"]
    )

    rear = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{TEST_VIN_2_EV}_recommended_tire_pressure_rear"
    )
    assert rear is not None
    assert (
        get_sensor_display_state(hass, entity_registry, rear)
        == EXPECTED_STATE_EV_METRIC["recommended_tire_pressure_rear"]
    )


async def test_avg_fuel_consumption_zero_metric(
    hass: HomeAssistant,
    subaru_config_entry: MockConfigEntry,
) -> None:
    """AVG_FUEL_CONSUMPTION of 0 returns 0 verbatim instead of dividing by zero.

    Guards the metric conversion at sensor.py:`native_value` so that a fresh
    vehicle reporting 0 mpg doesn't raise ZeroDivisionError on metric installs.
    """
    status_with_zero = copy.deepcopy(VEHICLE_STATUS_EV)
    status_with_zero[VEHICLE_STATUS]["AVG_FUEL_CONSUMPTION"] = 0

    await setup_subaru_config_entry(
        hass, subaru_config_entry, vehicle_status=status_with_zero
    )

    state = hass.states.get("sensor.test_vehicle_2_average_fuel_consumption")
    assert state is not None
    assert state.state == "0"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_enum_unmapped_value_and_raw_companion(
    hass: HomeAssistant,
    subaru_config_entry: MockConfigEntry,
) -> None:
    """Unmapped ENUM values report as `unknown`; the `_raw` companion surfaces the raw API string.

    Live API values not in `VEHICLE_STATE_OPTIONS` (etc.) are expected: the
    Subaru API is undocumented and the option list is what we have evidence
    for at release time. The ENUM sensor falls through to `unknown` for
    unknown inputs and the disabled-by-default `*_raw` companion sensor
    surfaces the raw upstream string so users can discover and report new
    values without us needing a stub release cycle.
    """
    status_with_unmapped_value = copy.deepcopy(VEHICLE_STATUS_EV)
    status_with_unmapped_value[VEHICLE_STATUS]["VEHICLE_STATE_TYPE"] = "ENGINE_RUNNING"

    await setup_subaru_config_entry(
        hass, subaru_config_entry, vehicle_status=status_with_unmapped_value
    )

    enum_state = hass.states.get("sensor.test_vehicle_2_vehicle_state")
    assert enum_state is not None
    assert enum_state.state == STATE_UNKNOWN

    raw_state = hass.states.get("sensor.test_vehicle_2_vehicle_state_raw")
    assert raw_state is not None
    assert raw_state.state == "ENGINE_RUNNING"
