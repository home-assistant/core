"""Tests for the pvpc_hourly_pricing component."""
from datetime import datetime
from unittest.mock import patch

from pytz import timezone

from homeassistant.components.pvpc_hourly_pricing import ATTR_TARIFF, DOMAIN
from homeassistant.const import CONF_NAME

from .conftest import check_valid_state

from tests.common import async_setup_component, date_util
from tests.test_util.aiohttp import AiohttpClientMocker


async def _test_setup_from_yaml_config(
    hass,
    aioclient_mock: AiohttpClientMocker,
    domain: str,
    config: dict,
    tariff: str = "discrimination",
):
    hass.config.time_zone = timezone("Atlantic/Canary")
    mock_data = {"return_time": datetime(2019, 10, 26, 13, 0, tzinfo=date_util.UTC)}

    def mock_now():
        return mock_data["return_time"]

    with patch("homeassistant.util.dt.utcnow", new=mock_now):
        assert await async_setup_component(hass, domain, config)
        await hass.async_block_till_done()
        state = hass.states.get("sensor.test")
        check_valid_state(state, tariff=tariff, key_attr="price_14h")

    assert aioclient_mock.call_count == 1


async def test_setup_as_integration(hass, pvpc_aioclient_mock: AiohttpClientMocker):
    """Test component setup creates entry from config and first state is valid."""
    tariff = "discrimination"
    config = {DOMAIN: [{CONF_NAME: "test", ATTR_TARIFF: tariff}]}
    await _test_setup_from_yaml_config(
        hass, pvpc_aioclient_mock, DOMAIN, config, tariff
    )


async def test_setup_as_sensor_platform(hass, pvpc_aioclient_mock: AiohttpClientMocker):
    """Test component setup creates entry from config as a sensor platform."""
    tariff = "normal"
    config_platform = {
        "sensor": {"platform": DOMAIN, CONF_NAME: "test", ATTR_TARIFF: tariff}
    }
    await _test_setup_from_yaml_config(
        hass, pvpc_aioclient_mock, "sensor", config_platform, tariff
    )
