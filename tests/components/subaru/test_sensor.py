"""Test Subaru sensors."""
from homeassistant.components.subaru.const import VEHICLE_NAME
from homeassistant.components.subaru.sensor import (
    API_GEN_2_SENSORS,
    EV_SENSORS,
    SAFETY_SENSORS,
    SENSOR_FIELD,
    SENSOR_TYPE,
)
from homeassistant.util import slugify
from homeassistant.util.unit_system import IMPERIAL_SYSTEM

from .api_responses import (
    EXPECTED_STATE_EV_IMPERIAL,
    EXPECTED_STATE_EV_METRIC,
    EXPECTED_STATE_EV_UNAVAILABLE,
    TEST_VIN_2_EV,
    VEHICLE_DATA,
    VEHICLE_STATUS_EV,
)

from tests.components.subaru.conftest import setup_subaru_integration

VEHICLE_NAME = VEHICLE_DATA[TEST_VIN_2_EV][VEHICLE_NAME]


async def test_sensors_ev_imperial(hass):
    """Test sensors supporting imperial units."""
    hass.config.units = IMPERIAL_SYSTEM
    await setup_subaru_integration(
        hass,
        vehicle_list=[TEST_VIN_2_EV],
        vehicle_data=VEHICLE_DATA[TEST_VIN_2_EV],
        vehicle_status=VEHICLE_STATUS_EV,
    )
    _assert_data(hass, EXPECTED_STATE_EV_IMPERIAL)


async def test_sensors_ev_metric(hass, ev_entry):
    """Test sensors supporting metric units."""
    _assert_data(hass, EXPECTED_STATE_EV_METRIC)


async def test_sensors_missing_vin_data(hass):
    """Test for missing VIN dataset."""
    await setup_subaru_integration(
        hass,
        vehicle_list=[TEST_VIN_2_EV],
        vehicle_data=VEHICLE_DATA[TEST_VIN_2_EV],
        vehicle_status=None,
    )
    _assert_data(hass, EXPECTED_STATE_EV_UNAVAILABLE)


def _assert_data(hass, expected_state):
    sensor_list = EV_SENSORS
    sensor_list.extend(API_GEN_2_SENSORS)
    sensor_list.extend(SAFETY_SENSORS)
    expected_states = {}
    for item in sensor_list:
        expected_states[
            f"sensor.{slugify(f'{VEHICLE_NAME} {item[SENSOR_TYPE]}')}"
        ] = expected_state[item[SENSOR_FIELD]]

    for sensor in expected_states:
        actual = hass.states.get(sensor)
        assert actual.state == expected_states[sensor]
