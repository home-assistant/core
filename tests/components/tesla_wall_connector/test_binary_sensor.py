"""Tests for binary sensors."""

from homeassistant.core import HomeAssistant

from .conftest import (
    EntityAndExpectedValues,
    _test_sensors,
    get_lifetime_mock,
    get_vitals_mock,
)


async def test_sensors(hass: HomeAssistant) -> None:
    """Test all binary sensors."""

    entity_and_expected_values = [
        EntityAndExpectedValues(
            "binary_sensor.tesla_wall_connector_contactor_closed", "off", "on"
        ),
        EntityAndExpectedValues(
            "binary_sensor.tesla_wall_connector_vehicle_connected", "on", "off"
        ),
    ]

    mock_vitals_first_update = get_vitals_mock()
    mock_vitals_first_update.contactor_closed = False
    mock_vitals_first_update.vehicle_connected = True

    mock_vitals_second_update = get_vitals_mock()
    mock_vitals_second_update.contactor_closed = True
    mock_vitals_second_update.vehicle_connected = False

    lifetime_mock = get_lifetime_mock()

    await _test_sensors(
        hass,
        entities_and_expected_values=entity_and_expected_values,
        vitals_first_update=mock_vitals_first_update,
        vitals_second_update=mock_vitals_second_update,
        lifetime_first_update=lifetime_mock,
        lifetime_second_update=lifetime_mock,
    )
