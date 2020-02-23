"""Tests for the pvpc_hourly_pricing component."""
from datetime import datetime, timedelta
from unittest.mock import patch

from pytz import timezone

from homeassistant.components.pvpc_hourly_pricing import ATTR_TARIFF, DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.core import ATTR_NOW, EVENT_TIME_CHANGED
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import check_valid_state


async def _process_time_step(
    hass, mock_data, key_state=None, value=None, delta_hours=1, tariff="discriminacion"
):
    state = hass.states.get("sensor.test_dst")
    check_valid_state(state, tariff=tariff, value=value, key_attr=key_state)

    mock_data["return_time"] += timedelta(hours=delta_hours)
    hass.bus.async_fire(EVENT_TIME_CHANGED, {ATTR_NOW: mock_data["return_time"]})
    await hass.async_block_till_done()
    return state


async def test_dst_spring_change(hass):
    """Test price sensor behavior in DST change day with 23 local hours."""
    hass.config.time_zone = timezone("Europe/Madrid")
    config = {DOMAIN: [{CONF_NAME: "test_dst", ATTR_TARIFF: "discriminacion"}]}
    mock_data = {"return_time": datetime(2019, 3, 30, 22, 0, tzinfo=dt_util.UTC)}

    def mock_now():
        return mock_data["return_time"]

    with patch("homeassistant.util.dt.utcnow", new=mock_now):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

        state = await _process_time_step(hass, mock_data, "price 23h", 0.07022)
        assert "price 02h" in state.attributes

        state = await _process_time_step(hass, mock_data, "price 00h", 0.07328)
        assert abs(state.attributes["price 01h"] - 0.07151) < 1e-6
        assert "price 02h" not in state.attributes  # that hour doesn't exist :)
        assert abs(state.attributes["price 03h"] - 0.0671) < 1e-6


async def test_dst_autumn_change(hass):
    """Test price sensor behavior in DST change day with 25 local hours."""
    hass.config.time_zone = timezone("Europe/Madrid")
    config = {DOMAIN: [{CONF_NAME: "test_dst", ATTR_TARIFF: "discriminacion"}]}
    mock_data = {"return_time": datetime(2019, 10, 26, 22, 0, 0, tzinfo=dt_util.UTC)}

    def mock_now():
        return mock_data["return_time"]

    with patch("homeassistant.util.dt.utcnow", new=mock_now):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

        state = await _process_time_step(hass, mock_data, "price 00h", 0.06595)
        assert abs(state.attributes["price 01h"] - 0.0606) < 1e-6
        assert abs(state.attributes["price 02h"] - 0.05938) < 1e-6
        assert abs(state.attributes["price 02h_d"] - 0.05931) < 1e-6
        assert abs(state.attributes["price 03h"] - 0.05816) < 1e-6
