"""Test the Anova sensors."""

import logging

from anova_wifi import AnovaApi

from homeassistant.components.anova import DOMAIN as ANOVA_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

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
    assert hass.states.get("sensor.anova_precision_cooker_state").state == ""
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


async def test_no_data_sensors(hass: HomeAssistant, anova_api_no_data: AnovaApi):
    """Test that if we have no data for the device, and we have not set it up previously, don't set up."""
    await async_init_integration(hass)
    assert hass.states.get("sensor.anova_precision_cooker_triac_temperature") is None


async def test_existing_sensors(
    hass: HomeAssistant,
    anova_api_no_data: AnovaApi,
    entity_registry: er.EntityRegistry,
):
    """Test that if we have no data for the device, and we have set it up previously, set it up."""
    # Remove any data from the websocket.
    entity_registry.async_get_or_create(
        ANOVA_DOMAIN, SENSOR_DOMAIN, "anova_id_triac_temperature"
    )
    await async_init_integration(hass)
    assert (
        hass.states.get("sensor.anova_precision_cooker_triac_temperature").state
        == STATE_UNAVAILABLE
    )
