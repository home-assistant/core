"""Tests for sensors."""

from homeassistant.core import HomeAssistant

from .conftest import (
    EntityAndExpectedValues,
    _test_sensors,
    get_lifetime_mock,
    get_vitals_mock,
)


async def test_sensors(hass: HomeAssistant) -> None:
    """Test all sensors."""

    entity_and_expected_values = [
        EntityAndExpectedValues(
            "sensor.tesla_wall_connector_status", "not_connected", "unknown"
        ),
        EntityAndExpectedValues(
            "sensor.tesla_wall_connector_handle_temperature", "25.5", "-1.4"
        ),
        EntityAndExpectedValues(
            "sensor.tesla_wall_connector_grid_voltage", "230.2", "229.2"
        ),
        EntityAndExpectedValues(
            "sensor.tesla_wall_connector_grid_frequency", "50.021", "49.981"
        ),
        EntityAndExpectedValues(
            "sensor.tesla_wall_connector_energy", "988.022", "989.000"
        ),
        EntityAndExpectedValues(
            "sensor.tesla_wall_connector_phase_a_current", "10", "7"
        ),
        EntityAndExpectedValues(
            "sensor.tesla_wall_connector_phase_b_current", "11.1", "8"
        ),
        EntityAndExpectedValues(
            "sensor.tesla_wall_connector_phase_c_current", "12", "9"
        ),
        EntityAndExpectedValues(
            "sensor.tesla_wall_connector_phase_a_voltage", "230.1", "228.1"
        ),
        EntityAndExpectedValues(
            "sensor.tesla_wall_connector_phase_b_voltage", "231", "229.1"
        ),
        EntityAndExpectedValues(
            "sensor.tesla_wall_connector_phase_c_voltage", "232.1", "230"
        ),
        EntityAndExpectedValues(
            "sensor.tesla_wall_connector_session_energy", "1.23456", "0.1122"
        ),
    ]

    mock_vitals_first_update = get_vitals_mock()
    mock_vitals_first_update.evse_state = 1
    mock_vitals_first_update.handle_temp_c = 25.51
    mock_vitals_first_update.grid_v = 230.15
    mock_vitals_first_update.grid_hz = 50.021
    mock_vitals_first_update.voltageA_v = 230.1
    mock_vitals_first_update.voltageB_v = 231
    mock_vitals_first_update.voltageC_v = 232.1
    mock_vitals_first_update.currentA_a = 10
    mock_vitals_first_update.currentB_a = 11.1
    mock_vitals_first_update.currentC_a = 12
    mock_vitals_first_update.session_energy_wh = 1234.56

    mock_vitals_second_update = get_vitals_mock()
    mock_vitals_second_update.evse_state = 3
    mock_vitals_second_update.handle_temp_c = -1.42
    mock_vitals_second_update.grid_v = 229.21
    mock_vitals_second_update.grid_hz = 49.981
    mock_vitals_second_update.voltageA_v = 228.1
    mock_vitals_second_update.voltageB_v = 229.1
    mock_vitals_second_update.voltageC_v = 230
    mock_vitals_second_update.currentA_a = 7
    mock_vitals_second_update.currentB_a = 8
    mock_vitals_second_update.currentC_a = 9
    mock_vitals_second_update.session_energy_wh = 112.2

    lifetime_mock_first_update = get_lifetime_mock()
    lifetime_mock_first_update.energy_wh = 988022
    lifetime_mock_second_update = get_lifetime_mock()
    lifetime_mock_second_update.energy_wh = 989000

    await _test_sensors(
        hass,
        entities_and_expected_values=entity_and_expected_values,
        vitals_first_update=mock_vitals_first_update,
        vitals_second_update=mock_vitals_second_update,
        lifetime_first_update=lifetime_mock_first_update,
        lifetime_second_update=lifetime_mock_second_update,
    )
