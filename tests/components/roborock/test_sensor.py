"""Test Roborock Sensors."""

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_sensors(hass: HomeAssistant, setup_entry: MockConfigEntry) -> None:
    """Test sensors and check test values are correctly set."""
    assert len(hass.states.async_all("sensor")) == 4
    assert (
        hass.states.get("sensor.roborock_s7_maxv_main_brush_work_time").state == "74382"
    )
    assert (
        hass.states.get("sensor.roborock_s7_maxv_side_brush_work_time").state == "74382"
    )
    assert hass.states.get("sensor.roborock_s7_maxv_filter_work_time").state == "74382"
    assert hass.states.get("sensor.roborock_s7_maxv_sensor_work_time").state == "74382"
