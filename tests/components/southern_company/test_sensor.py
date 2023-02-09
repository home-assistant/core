"""Test sensors for Southern Company."""

from homeassistant.core import HomeAssistant

from tests.components.southern_company import async_init_integration


async def test_sensors(recorder_mock, hass: HomeAssistant):
    """Test setting up the sensors."""
    await async_init_integration(hass)
    assert len(hass.states.async_all("sensor")) == 8
    assert hass.states.get("sensor.monthly_cost").state == "1.0"
    assert hass.states.get("sensor.monthly_net_consumption").state == "2.0"
    assert hass.states.get("sensor.average_daily_usage").state == "3.0"
    assert hass.states.get("sensor.average_daily_cost").state == "4.0"
    assert hass.states.get("sensor.lower_projected_monthly_usage").state == "5.0"
    assert hass.states.get("sensor.higher_projected_monthly_usage").state == "6.0"
    assert hass.states.get("sensor.lower_projected_monthly_cost").state == "7.0"
    assert hass.states.get("sensor.higher_projected_monthly_cost").state == "8.0"
