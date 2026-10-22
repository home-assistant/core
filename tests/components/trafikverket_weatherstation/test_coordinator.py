"""Test the Trafikverket Weatherstation coordinator."""

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytrafikverket.exceptions import (
    MultipleWeatherStationsFound,
    NoWeatherStationFound,
    UnknownError,
)

from homeassistant.components.trafikverket_weatherstation.coordinator import (
    TIME_BETWEEN_UPDATES,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

ENTITY_ID = "sensor.arlanda_air_temperature"


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(NoWeatherStationFound, id="no_station"),
        pytest.param(MultipleWeatherStationsFound, id="multiple_stations"),
        pytest.param(UnknownError, id="unknown_error"),
    ],
)
async def test_coordinator_update_failed(
    hass: HomeAssistant,
    load_int: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    side_effect: type[Exception],
) -> None:
    """Test update failures are logged once and mark entities unavailable."""
    assert hass.states.get(ENTITY_ID).state == "-3.0"

    with patch(
        "homeassistant.components.trafikverket_weatherstation.coordinator.TrafikverketWeather.async_get_weather",
        side_effect=side_effect,
    ):
        for _ in range(2):
            freezer.tick(TIME_BETWEEN_UPDATES)
            async_fire_time_changed(hass)
            await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert caplog.text.count("Error fetching trafikverket_weatherstation data") == 1
    assert "Unexpected error fetching" not in caplog.text
