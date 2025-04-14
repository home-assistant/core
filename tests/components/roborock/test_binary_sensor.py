"""Test Roborock Binary Sensor."""

import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set platforms used in the test."""
    return [Platform.BINARY_SENSOR]


async def test_binary_sensors(
    hass: HomeAssistant, setup_entry: MockConfigEntry
) -> None:
    """Test binary sensors and check test values are correctly set."""
    assert len(hass.states.async_all("binary_sensor")) == 10
    assert hass.states.get("binary_sensor.roborock_s7_maxv_mop_attached").state == "on"
    assert (
        hass.states.get("binary_sensor.roborock_s7_maxv_water_box_attached").state
        == "on"
    )
    assert (
        hass.states.get("binary_sensor.roborock_s7_maxv_water_shortage").state == "off"
    )
    assert hass.states.get("binary_sensor.roborock_s7_maxv_cleaning").state == "off"
    assert hass.states.get("binary_sensor.roborock_s7_maxv_charging").state == "on"
