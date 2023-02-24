"""Test sensors for Southern Company."""

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.recorder.core import Recorder
from homeassistant.components.southern_company.coordinator import (
    SouthernCompanyCoordinator,
)
from homeassistant.components.southern_company.sensor import (
    SouthernCompanyEntityDescription,
    SouthernCompanySensor,
)
from homeassistant.core import HomeAssistant

from . import async_init_integration


async def test_sensors(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test setting up the sensors."""
    await async_init_integration(hass)
    assert len(hass.states.async_all("sensor")) == 8
    assert hass.states.get("sensor.monthly_cost").state == "1.0"
    assert hass.states.get("sensor.monthly_consumption").state == "2.0"
    assert hass.states.get("sensor.average_daily_usage").state == "3.0"
    assert hass.states.get("sensor.average_daily_cost").state == "4.0"
    assert hass.states.get("sensor.lower_projected_monthly_usage").state == "5.0"
    assert hass.states.get("sensor.higher_projected_monthly_usage").state == "6.0"
    assert hass.states.get("sensor.lower_projected_monthly_cost").state == "7.0"
    assert hass.states.get("sensor.higher_projected_monthly_cost").state == "8.0"


async def test_empty_sensor(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test that when the coordinator has not been setup, sensor has None for its value."""
    api_mock = AsyncMock()
    coordinator = SouthernCompanyCoordinator(hass, api_mock)
    sample_account = MagicMock()
    description = SouthernCompanyEntityDescription(
        key="sample",
        name="Sample",
        value_fn=lambda data: data.projected_bill_amount_low,
    )

    sensor = SouthernCompanySensor(
        sample_account, coordinator, description, MagicMock()
    )
    assert sensor.native_value is None
