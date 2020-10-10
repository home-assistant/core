"""Test Subaru sensors."""

from homeassistant.components.subaru.const import VEHICLE_NAME
from homeassistant.components.subaru.sensor import (
    API_GEN_2_SENSORS,
    EV_SENSORS,
    SAFETY_SENSORS,
    SENSOR_FIELD,
    SENSOR_NAME,
)
from homeassistant.util import slugify
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM

from .api_responses import (
    EXPECTED_STATE_EV_IMPERIAL,
    EXPECTED_STATE_EV_METRIC,
    TEST_VIN_2_EV,
    VEHICLE_DATA,
    VEHICLE_STATUS_EV,
)
from .test_init import setup_subaru_integration

from tests.async_mock import patch


async def test_sensors_ev_imperial(hass):
    """Test sensors supporting imperial units."""
    with patch("homeassistant.components.subaru.config_flow.SubaruAPI.fetch"), patch(
        "homeassistant.components.subaru.config_flow.SubaruAPI.get_data",
        return_value=VEHICLE_STATUS_EV,
    ):
        await _setup_ev(hass, unit_system=IMPERIAL_SYSTEM)

        sensor_list = EV_SENSORS
        sensor_list.extend(API_GEN_2_SENSORS)
        sensor_list.extend(SAFETY_SENSORS)
        expected = _get_expected(
            VEHICLE_DATA[TEST_VIN_2_EV][VEHICLE_NAME],
            sensor_list,
            EXPECTED_STATE_EV_IMPERIAL,
        )

        for sensor in expected:
            actual = hass.states.get(sensor)
            assert actual.state == expected[sensor]


async def test_sensors_ev_metric(hass):
    """Test sensors supporting metric units."""
    with patch("homeassistant.components.subaru.config_flow.SubaruAPI.fetch"), patch(
        "homeassistant.components.subaru.config_flow.SubaruAPI.get_data",
        return_value=VEHICLE_STATUS_EV,
    ):
        await _setup_ev(hass)

        sensor_list = EV_SENSORS
        sensor_list.extend(API_GEN_2_SENSORS)
        sensor_list.extend(SAFETY_SENSORS)
        expected = _get_expected(
            VEHICLE_DATA[TEST_VIN_2_EV][VEHICLE_NAME],
            sensor_list,
            EXPECTED_STATE_EV_METRIC,
        )

        for sensor in expected:
            actual = hass.states.get(sensor)
            assert actual.state == expected[sensor]


def _get_expected(vehicle_name, sensor_list, expected_state):
    expected = {}
    for item in sensor_list:
        expected[
            f"sensor.{slugify(f'{vehicle_name} {item[SENSOR_NAME]}')}"
        ] = expected_state[item[SENSOR_FIELD]]
    return expected


async def _setup_ev(hass, unit_system=METRIC_SYSTEM):
    hass.config.units = unit_system
    return await setup_subaru_integration(
        hass,
        vehicle_list=[TEST_VIN_2_EV],
        vehicle_data=VEHICLE_DATA[TEST_VIN_2_EV],
        vehicle_status=VEHICLE_STATUS_EV,
    )
