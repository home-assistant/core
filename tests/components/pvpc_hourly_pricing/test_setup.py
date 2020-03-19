"""Tests for the pvpc_hourly_pricing component."""
from datetime import datetime
from unittest.mock import patch

from pytz import timezone

from homeassistant.components.pvpc_hourly_pricing import ATTR_TARIFF, DOMAIN
from homeassistant.const import CONF_NAME

from .conftest import check_valid_state

from tests.common import async_setup_component, date_util
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup_as_integration(hass, pvpc_aioclient_mock: AiohttpClientMocker):
    """Test component setup creates entry from config and first state is valid."""
    hass.config.time_zone = timezone("Atlantic/Canary")
    mock_data = {"return_time": datetime(2019, 10, 26, 13, 0, tzinfo=date_util.UTC)}
    tariff = "discrimination"
    config = {DOMAIN: [{CONF_NAME: "test", ATTR_TARIFF: tariff}]}

    def mock_now():
        return mock_data["return_time"]

    with patch("homeassistant.util.dt.utcnow", new=mock_now):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        state = hass.states.get("sensor.test")
        check_valid_state(state, tariff=tariff, key_attr="price_14h")

    assert pvpc_aioclient_mock.call_count == 1
