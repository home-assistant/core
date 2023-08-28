"""The tests for weather recorder."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.components.weather import ATTR_CONDITION_SUNNY, ATTR_FORECAST
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_system import METRIC_SYSTEM

from tests.common import async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done
from tests.testing_config.custom_components.test import weather as WeatherPlatform


async def create_entity(hass: HomeAssistant, **kwargs):
    """Create the weather entity to run tests on."""
    kwargs = {
        "native_temperature": None,
        "native_temperature_unit": None,
        "is_daytime": True,
        **kwargs,
    }
    platform: WeatherPlatform = getattr(hass.components, "test.weather")
    platform.init(empty=True)
    platform.ENTITIES.append(
        platform.MockWeatherMockForecast(
            name="Test", condition=ATTR_CONDITION_SUNNY, **kwargs
        )
    )

    entity0 = platform.ENTITIES[0]
    assert await async_setup_component(
        hass, "weather", {"weather": {"platform": "test"}}
    )
    await hass.async_block_till_done()
    return entity0


async def test_exclude_attributes(
    recorder_mock: Recorder, hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test weather attributes to be excluded."""
    now = dt_util.utcnow()
    entity0 = await create_entity(
        hass,
        native_temperature=38,
        native_temperature_unit=UnitOfTemperature.CELSIUS,
    )
    hass.config.units = METRIC_SYSTEM
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert state.attributes[ATTR_FORECAST]

    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    states = await hass.async_add_executor_job(
        get_significant_states, hass, now, None, hass.states.async_entity_ids()
    )
    assert len(states) >= 1
    for entity_states in states.values():
        for state in entity_states:
            assert ATTR_FORECAST not in state.attributes
