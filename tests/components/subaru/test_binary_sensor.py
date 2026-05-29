"""Test Subaru binary sensors."""

import pytest

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.subaru.binary_sensor import (
    DOOR_BINARY_SENSORS,
    LOCK_BINARY_SENSORS,
    MIL_TRANSLATION_KEYS,
    WINDOW_BINARY_SENSORS,
)
from homeassistant.components.subaru.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .api_responses import (
    TEST_VIN_1_G1,
    TEST_VIN_2_EV,
    TEST_VIN_3_G3,
    VEHICLE_DATA,
    VEHICLE_STATUS_G3,
)
from .conftest import setup_subaru_config_entry

from tests.common import MockConfigEntry


def _unique_id(vin: str, key: str) -> str:
    return f"{vin}_{key}"


@pytest.mark.usefixtures("ev_entry")
async def test_binary_sensors_present_for_ev(
    entity_registry: er.EntityRegistry,
) -> None:
    """All openings + read-only locks + overall health entity exist for EVs."""
    for desc in DOOR_BINARY_SENSORS + WINDOW_BINARY_SENSORS + LOCK_BINARY_SENSORS:
        entity = entity_registry.async_get_entity_id(
            BINARY_SENSOR_DOMAIN, DOMAIN, _unique_id(TEST_VIN_2_EV, desc.key)
        )
        assert entity is not None, f"missing entity for {desc.key}"

    overall = entity_registry.async_get_entity_id(
        BINARY_SENSOR_DOMAIN, DOMAIN, _unique_id(TEST_VIN_2_EV, "health_istrouble")
    )
    assert overall is not None


@pytest.mark.parametrize(
    ("entity_id", "expected_state"),
    [
        pytest.param(
            "binary_sensor.test_vehicle_2_door_front_left",
            STATE_OFF,
            id="closed_door_is_off",
        ),
        pytest.param(
            "binary_sensor.test_vehicle_2_window_front_left",
            STATE_ON,
            id="vented_window_is_on",
        ),
        pytest.param(
            "binary_sensor.test_vehicle_2_window_rear_left",
            STATE_UNKNOWN,
            id="unknown_window_is_unknown",
        ),
        pytest.param(
            "binary_sensor.test_vehicle_2_lock_status_front_left",
            STATE_OFF,
            id="locked_door_lock_is_off_per_LOCK_device_class",
        ),
        pytest.param(
            "binary_sensor.test_vehicle_2_vehicle_health",
            STATE_OFF,
            id="overall_istrouble_false_is_off",
        ),
    ],
)
@pytest.mark.usefixtures("ev_entry")
async def test_binary_sensor_states_for_ev(
    hass: HomeAssistant,
    entity_id: str,
    expected_state: str,
) -> None:
    """Each opening/lock/health entity reports the state derived from the API value."""
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.parametrize("feature", ["TPMS_MIL", "CEL_MIL"])
@pytest.mark.usefixtures("ev_entry")
async def test_mil_entities_disabled_by_default(
    entity_registry: er.EntityRegistry,
    feature: str,
) -> None:
    """MIL entities are created for reported MIL features and disabled by default."""
    entity_id = entity_registry.async_get_entity_id(
        BINARY_SENSOR_DOMAIN, DOMAIN, _unique_id(TEST_VIN_2_EV, feature)
    )
    assert entity_id is not None
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert entry.translation_key == MIL_TRANSLATION_KEYS[feature]


async def test_no_binary_sensors_for_g1(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    subaru_config_entry: MockConfigEntry,
) -> None:
    """Gen1 vehicles do not get any binary sensors (no door/lock/health data)."""
    await setup_subaru_config_entry(
        hass,
        subaru_config_entry,
        vehicle_list=[TEST_VIN_1_G1],
        vehicle_data=VEHICLE_DATA[TEST_VIN_1_G1],
    )
    for desc in DOOR_BINARY_SENSORS:
        assert (
            entity_registry.async_get_entity_id(
                BINARY_SENSOR_DOMAIN, DOMAIN, _unique_id(TEST_VIN_1_G1, desc.key)
            )
            is None
        )


async def test_binary_sensors_for_g3(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    subaru_config_entry: MockConfigEntry,
) -> None:
    """Gen3 vehicles get openings/locks/overall-health entities even without vehicle_features."""
    await setup_subaru_config_entry(
        hass,
        subaru_config_entry,
        vehicle_list=[TEST_VIN_3_G3],
        vehicle_data=VEHICLE_DATA[TEST_VIN_3_G3],
        vehicle_status=VEHICLE_STATUS_G3,
    )
    overall = entity_registry.async_get_entity_id(
        BINARY_SENSOR_DOMAIN, DOMAIN, _unique_id(TEST_VIN_3_G3, "health_istrouble")
    )
    assert overall is not None
    state = hass.states.get(overall)
    assert state is not None
    # Without vehicle_health in the mock, the rollup reports unknown.
    assert state.state == STATE_UNKNOWN
