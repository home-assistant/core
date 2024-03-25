"""Test the HaFAS sensor device."""

from datetime import datetime

from homeassistant.components.hafas.const import DOMAIN
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from .common import setup_platform


async def test_attributes(hass: HomeAssistant) -> None:
    """Test the sensor attributes are correct."""
    await setup_platform(hass, DOMAIN)

    state = hass.states.get("sensor.mock_title")

    assert state.state == "12:30"
    assert dt_util.as_utc(state.attributes.get("departure")) == datetime(
        2022, 10, 1, 10, 30, tzinfo=dt_util.UTC
    )
    assert dt_util.as_utc(state.attributes.get("arrival")) == datetime(
        2022, 10, 1, 11, 42, tzinfo=dt_util.UTC
    )
    assert state.attributes.get("transfers") == 0
    assert state.attributes.get("time") == "1:12:00"
    assert state.attributes.get("products") == "ICE 5"
    assert state.attributes.get("ontime") is True
    assert state.attributes.get("delay") == "0:00:00"
    assert state.attributes.get("canceled") is False
    assert state.attributes.get("delay_arrival") == "0:00:00"
    assert dt_util.as_utc(state.attributes.get("next")) == datetime(
        2022, 10, 1, 11, 28, tzinfo=dt_util.UTC
    )
    assert dt_util.as_utc(state.attributes.get("next_on")) == datetime(
        2022, 10, 1, 11, 37, tzinfo=dt_util.UTC
    )
