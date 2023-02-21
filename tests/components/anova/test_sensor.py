"""Test the Anova sensors."""

import logging
from unittest.mock import patch

from anova_wifi import AnovaOffline, AnovaPrecisionCooker
import pytest

from homeassistant import config_entries
from homeassistant.components.anova.coordinator import AnovaCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import async_init_integration, create_entry

LOGGER = logging.getLogger(__name__)


async def test_sensors(hass: HomeAssistant) -> None:
    """Test setting up creates the sensors."""
    await async_init_integration(hass)
    assert len(hass.states.async_all("sensor")) == 8
    assert hass.states.get("sensor.cook_time_remaining").state == "0"
    assert hass.states.get("sensor.cook_time").state == "0"
    assert hass.states.get("sensor.heater_temperature").state == "20.87"
    assert hass.states.get("sensor.mode").state == "Low water"
    assert hass.states.get("sensor.state").state == "No state"
    assert hass.states.get("sensor.target_temperature").state == "23.33"
    assert hass.states.get("sensor.water_temperature").state == "21.33"
    assert hass.states.get("sensor.triac_temperature").state == "21.79"


async def test_no_config_entry_coordinator(hass: HomeAssistant) -> None:
    """Test setting up coordinator without config entry, I don't think this is possible, but I got a lint error with accessing a None when I did self.config_entry."""
    with pytest.raises(AssertionError):
        AnovaCoordinator(hass, None)


async def test_update_failed(hass: HomeAssistant) -> None:
    """Test updating data after the coordinator has been set up, but anova is offline."""
    with pytest.raises(UpdateFailed):
        entry = create_entry(hass)
        config_entries.current_entry.set(entry)
        ac = AnovaCoordinator(hass, AnovaPrecisionCooker(None))
        with patch(
            "homeassistant.components.anova.AnovaPrecisionCooker.update",
            side_effect=AnovaOffline(),
        ):
            await ac._async_update_data()
