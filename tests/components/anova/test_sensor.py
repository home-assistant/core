"""Test the Anova sensors."""

import logging

from anova_wifi import AnovaApi
import pytest

from homeassistant.core import HomeAssistant

from . import async_init_integration

LOGGER = logging.getLogger(__name__)


async def test_sensors(hass: HomeAssistant, anova_api: AnovaApi) -> None:
    """Test setting up creates the sensors."""
    await async_init_integration(hass)
    assert len(hass.states.async_all("sensor")) == 8
    assert (
        hass.states.get("sensor.anova_precision_cooker_cook_time_remaining").state
        == "0"
    )
    assert hass.states.get("sensor.anova_precision_cooker_cook_time").state == "0"
    assert (
        hass.states.get("sensor.anova_precision_cooker_heater_temperature").state
        == "22.37"
    )
    assert hass.states.get("sensor.anova_precision_cooker_mode").state == "idle"
    assert hass.states.get("sensor.anova_precision_cooker_state").state == "no_state"
    assert (
        hass.states.get("sensor.anova_precision_cooker_target_temperature").state
        == "54.72"
    )
    assert (
        hass.states.get("sensor.anova_precision_cooker_water_temperature").state
        == "18.33"
    )
    assert (
        hass.states.get("sensor.anova_precision_cooker_triac_temperature").state
        == "36.04"
    )


@pytest.mark.usefixtures("anova_api_no_data")
async def test_no_data_sensors(hass: HomeAssistant) -> None:
    """Test that if we have no data for the device, and we have not set it up previously, It is not immediately set up."""
    await async_init_integration(hass)
    assert hass.states.get("sensor.anova_precision_cooker_triac_temperature") is None
