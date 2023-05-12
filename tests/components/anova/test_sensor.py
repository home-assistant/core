"""Test the Anova sensors."""

from datetime import timedelta
import logging
from unittest.mock import patch

from anova_wifi import AnovaApi, AnovaOffline

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt

from . import async_init_integration

from tests.common import async_fire_time_changed

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
        == "20.87"
    )
    assert hass.states.get("sensor.anova_precision_cooker_mode").state == "Low water"
    assert hass.states.get("sensor.anova_precision_cooker_state").state == "No state"
    assert (
        hass.states.get("sensor.anova_precision_cooker_target_temperature").state
        == "23.33"
    )
    assert (
        hass.states.get("sensor.anova_precision_cooker_water_temperature").state
        == "21.33"
    )
    assert (
        hass.states.get("sensor.anova_precision_cooker_triac_temperature").state
        == "21.79"
    )


async def test_update_failed(hass: HomeAssistant, anova_api: AnovaApi) -> None:
    """Test updating data after the coordinator has been set up, but anova is offline."""
    await async_init_integration(hass)
    await hass.async_block_till_done()
    with patch(
        "homeassistant.components.anova.AnovaPrecisionCooker.update",
        side_effect=AnovaOffline(),
    ):
        async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=61))
        await hass.async_block_till_done()

        state = hass.states.get("sensor.anova_precision_cooker_water_temperature")
        assert state.state == STATE_UNAVAILABLE
