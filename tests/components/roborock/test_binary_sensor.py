"""Test Roborock Binary Sensor."""

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_binary_sensors(
    hass: HomeAssistant, setup_entry: MockConfigEntry
) -> None:
    """Test binary sensors and check test values are correctly set."""
    assert len(hass.states.async_all("binary_sensor")) == 2
    assert hass.states.get("binary_sensor.roborock_s7_maxv_mop_attached").state == "on"
    assert (
        hass.states.get("binary_sensor.roborock_s7_maxv_water_box_attached").state
        == "on"
    )
