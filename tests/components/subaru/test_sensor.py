"""Test Subaru sensors."""
from unittest.mock import patch

from homeassistant.components.subaru.const import (
    DOMAIN,
    REMOTE_SERVICE_FETCH,
    VEHICLE_NAME,
    VEHICLE_VIN,
)
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
    TEST_VIN_2_EV,
    VEHICLE_DATA,
    VEHICLE_STATUS_EV,
)

from tests.components.subaru.conftest import MOCK_API_FETCH, MOCK_API_GET_GET_DATA

VEHICLE_NAME = VEHICLE_DATA[TEST_VIN_2_EV][VEHICLE_NAME]


async def test_sensors_ev_imperial(hass, ev_entry):
    """Test sensors supporting imperial units."""
    with patch(MOCK_API_FETCH), patch(
        MOCK_API_GET_GET_DATA,
        return_value=VEHICLE_STATUS_EV,
    ):
        hass.config.units = IMPERIAL_SYSTEM
        await hass.services.async_call(
            DOMAIN,
            REMOTE_SERVICE_FETCH,
            {VEHICLE_VIN: TEST_VIN_2_EV},
            blocking=True,
        )
        await hass.async_block_till_done()

    _assert_data(hass, EXPECTED_STATE_EV_IMPERIAL)


async def test_sensors_ev_metric(hass, ev_entry):
    """Test sensors supporting metric units."""
    _assert_data(hass, EXPECTED_STATE_EV_METRIC)


async def test_sensors_missing_vin_data(hass, ev_entry):
    """Test for missing VIN dataset."""
    with patch(MOCK_API_FETCH), patch(
        MOCK_API_GET_GET_DATA,
        return_value=None,
    ):
        await hass.services.async_call(
            DOMAIN,
            REMOTE_SERVICE_FETCH,
            {VEHICLE_VIN: TEST_VIN_2_EV},
            blocking=True,
        )
        await hass.async_block_till_done()


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
