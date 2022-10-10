"""Test Subaru sensors."""
from unittest.mock import patch

import pytest

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.subaru.sensor import (
    API_GEN_2_SENSORS,
    DOMAIN as SUBARU_DOMAIN,
    EV_SENSORS,
    SAFETY_SENSORS,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .api_responses import (
    EXPECTED_STATE_EV_IMPERIAL,
    EXPECTED_STATE_EV_METRIC,
    EXPECTED_STATE_EV_UNAVAILABLE,
    TEST_VIN_2_EV,
    VEHICLE_DATA,
    VEHICLE_STATUS_EV,
)
from .conftest import (
    MOCK_API_FETCH,
    MOCK_API_GET_DATA,
    TEST_CONFIG_ENTRY,
    TEST_DEVICE_NAME,
    advance_time_to_next_fetch,
    setup_subaru_integration,
)

from tests.common import MockConfigEntry


async def test_sensors_ev_imperial(hass, ev_entry):
    """Test sensors supporting imperial units."""
    hass.config.units = US_CUSTOMARY_SYSTEM

    with patch(MOCK_API_FETCH), patch(
        MOCK_API_GET_DATA, return_value=VEHICLE_STATUS_EV
    ):
        advance_time_to_next_fetch(hass)
        await hass.async_block_till_done()

    _assert_data(hass, EXPECTED_STATE_EV_IMPERIAL)


async def test_sensors_ev_metric(hass, ev_entry):
    """Test sensors supporting metric units."""
    _assert_data(hass, EXPECTED_STATE_EV_METRIC)


async def test_sensors_missing_vin_data(hass, ev_entry):
    """Test for missing VIN dataset."""
    with patch(MOCK_API_FETCH), patch(MOCK_API_GET_DATA, return_value=None):
        advance_time_to_next_fetch(hass)
        await hass.async_block_till_done()

    _assert_data(hass, EXPECTED_STATE_EV_UNAVAILABLE)


@pytest.mark.parametrize(
    "entitydata,old_unique_id,new_unique_id",
    [
        (
            {
                "domain": SENSOR_DOMAIN,
                "platform": SUBARU_DOMAIN,
                "unique_id": f"{TEST_VIN_2_EV}_{API_GEN_2_SENSORS[0].name}",
            },
            f"{TEST_VIN_2_EV}_{API_GEN_2_SENSORS[0].name}",
            f"{TEST_VIN_2_EV}_{API_GEN_2_SENSORS[0].key}",
        ),
    ],
)
async def test_sensor_migrate_unique_ids(
    hass,
    entitydata,
    old_unique_id,
    new_unique_id,
) -> None:
    """Test successful migration of entity unique_ids."""
    mock_config_entry = MockConfigEntry(**TEST_CONFIG_ENTRY)
    mock_config_entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)
    entity: er.RegistryEntry = entity_registry.async_get_or_create(
        **entitydata,
        config_entry=mock_config_entry,
    )
    assert entity.unique_id == old_unique_id

    await setup_subaru_integration(
        hass,
        mock_config_entry=mock_config_entry,
        vehicle_list=[TEST_VIN_2_EV],
        vehicle_data=VEHICLE_DATA[TEST_VIN_2_EV],
        vehicle_status=VEHICLE_STATUS_EV,
    )

    entity_migrated = entity_registry.async_get(entity.entity_id)
    assert entity_migrated
    assert entity_migrated.unique_id == new_unique_id


@pytest.mark.parametrize(
    "entitydata,old_unique_id,new_unique_id",
    [
        (
            {
                "domain": SENSOR_DOMAIN,
                "platform": SUBARU_DOMAIN,
                "unique_id": f"{TEST_VIN_2_EV}_{API_GEN_2_SENSORS[0].name}",
            },
            f"{TEST_VIN_2_EV}_{API_GEN_2_SENSORS[0].name}",
            f"{TEST_VIN_2_EV}_{API_GEN_2_SENSORS[0].key}",
        )
    ],
)
async def test_sensor_migrate_unique_ids_duplicate(
    hass,
    entitydata,
    old_unique_id,
    new_unique_id,
) -> None:
    """Test unsuccessful migration of entity unique_ids due to duplicate."""
    mock_config_entry = MockConfigEntry(**TEST_CONFIG_ENTRY)
    mock_config_entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)
    entity: er.RegistryEntry = entity_registry.async_get_or_create(
        **entitydata,
        config_entry=mock_config_entry,
    )
    assert entity.unique_id == old_unique_id

    # create existing entry with new_unique_id that conflicts with migrate
    existing_entity = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        SUBARU_DOMAIN,
        unique_id=new_unique_id,
        config_entry=mock_config_entry,
    )

    await setup_subaru_integration(
        hass,
        mock_config_entry=mock_config_entry,
        vehicle_list=[TEST_VIN_2_EV],
        vehicle_data=VEHICLE_DATA[TEST_VIN_2_EV],
        vehicle_status=VEHICLE_STATUS_EV,
    )

    entity_migrated = entity_registry.async_get(entity.entity_id)
    assert entity_migrated
    assert entity_migrated.unique_id == old_unique_id

    entity_not_changed = entity_registry.async_get(existing_entity.entity_id)
    assert entity_not_changed
    assert entity_not_changed.unique_id == new_unique_id

    assert entity_migrated != entity_not_changed


def _assert_data(hass, expected_state):
    sensor_list = EV_SENSORS
    sensor_list.extend(API_GEN_2_SENSORS)
    sensor_list.extend(SAFETY_SENSORS)
    expected_states = {}
    for item in sensor_list:
        expected_states[
            f"sensor.{slugify(f'{TEST_DEVICE_NAME} {item.name}')}"
        ] = expected_state[item.key]

    for sensor, value in expected_states.items():
        actual = hass.states.get(sensor)
        assert actual.state == value
