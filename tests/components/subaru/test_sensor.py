"""Test Subaru sensors."""
from datetime import datetime
from unittest.mock import patch

from homeassistant.components.subaru.const import DOMAIN, VEHICLE_NAME
from homeassistant.components.subaru.sensor import (
    API_GEN_2_SENSORS,
    EV_SENSORS,
    SAFETY_SENSORS,
    SENSOR_FIELD,
    SENSOR_TYPE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.util import slugify
from homeassistant.util.unit_system import IMPERIAL_SYSTEM

from .api_responses import (
    EXPECTED_STATE_EV_IMPERIAL,
    EXPECTED_STATE_EV_INVALID_DATA,
    EXPECTED_STATE_EV_METRIC,
    EXPECTED_STATE_EV_UNAVAILABLE,
    TEST_VIN_2_EV,
    VEHICLE_DATA,
    VEHICLE_STATUS_EV,
    VEHICLE_STATUS_EV_INVALID_ITEMS,
)
from .conftest import (
    MOCK_API_FETCH,
    MOCK_API_GET_DATA,
    advance_time_to_next_fetch,
    setup_subaru_integration,
)

VEHICLE_NAME = VEHICLE_DATA[TEST_VIN_2_EV][VEHICLE_NAME]


async def test_sensors_ev_imperial(hass, ev_entry):
    """Test sensors supporting imperial units."""
    hass.config.units = IMPERIAL_SYSTEM

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


async def test_sensors_invalid_data(hass):
    """Test when VIN dataset includes bad values."""
    entry = await setup_subaru_integration(
        hass,
        vehicle_list=[TEST_VIN_2_EV],
        vehicle_data=VEHICLE_DATA[TEST_VIN_2_EV],
        vehicle_status=VEHICLE_STATUS_EV_INVALID_ITEMS,
    )
    assert DOMAIN in hass.config_entries.async_domains()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert hass.config_entries.async_get_entry(entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED

    _assert_data(hass, EXPECTED_STATE_EV_INVALID_DATA)


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
        if isinstance(expected_states[sensor], datetime):
            assert actual.state == expected_states[sensor].isoformat()
        else:
            assert actual.state == expected_states[sensor]
