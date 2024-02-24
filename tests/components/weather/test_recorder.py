"""The tests for weather recorder."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.components.weather import ATTR_FORECAST, Forecast
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_system import METRIC_SYSTEM

from . import MockWeatherTest, create_entity

from tests.common import async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done


async def test_exclude_attributes(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    config_flow_fixture: None,
) -> None:
    """Test weather attributes to be excluded."""
    now = dt_util.utcnow()

    class MockWeatherMockForecast(MockWeatherTest):
        """Mock weather class with mocked legacy forecast."""

        @property
        def forecast(self) -> list[Forecast] | None:
            """Return the forecast."""
            return self.forecast_list

    kwargs = {
        "native_temperature": 38,
        "native_temperature_unit": UnitOfTemperature.CELSIUS,
    }
    weather_entity = await create_entity(hass, MockWeatherMockForecast, None, **kwargs)
    hass.config.units = METRIC_SYSTEM
    await hass.async_block_till_done()

    state = hass.states.get(weather_entity.entity_id)
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
