"""Test Subaru sensors."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.subaru.sensor import (
    API_GEN_2_SENSORS,
    DOMAIN as SUBARU_DOMAIN,
    EV_SENSORS,
    SAFETY_SENSORS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .api_responses import (
    EXPECTED_STATE_EV_METRIC,
    EXPECTED_STATE_EV_UNAVAILABLE,
    TEST_VIN_2_EV,
)
from .conftest import (
    MOCK_API_FETCH,
    MOCK_API_GET_DATA,
    advance_time_to_next_fetch,
    setup_subaru_config_entry,
)


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
                "platform": SUBARU_DOMAIN,
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
                "platform": SUBARU_DOMAIN,
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
        SUBARU_DOMAIN,
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
        entity = entity_registry.async_get_entity_id(
            SENSOR_DOMAIN, SUBARU_DOMAIN, f"{TEST_VIN_2_EV}_{item.key}"
        )
        expected_states[entity] = expected_state[item.key]

    for sensor, value in expected_states.items():
        actual = hass.states.get(sensor)
        assert actual.state == value
