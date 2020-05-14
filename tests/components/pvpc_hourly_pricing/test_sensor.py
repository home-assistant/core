"""Tests for the pvpc_hourly_pricing sensor component."""
from datetime import datetime, timedelta
import logging
from unittest.mock import patch

from pytz import timezone

from homeassistant.components.pvpc_hourly_pricing import ATTR_TARIFF, DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.core import ATTR_NOW, EVENT_TIME_CHANGED

from .conftest import check_valid_state

from tests.common import async_setup_component, date_util
from tests.test_util.aiohttp import AiohttpClientMocker


async def _process_time_step(
    hass, mock_data, key_state=None, value=None, tariff="discrimination", delta_min=60
):
    state = hass.states.get("sensor.test_dst")
    check_valid_state(state, tariff=tariff, value=value, key_attr=key_state)

    mock_data["return_time"] += timedelta(minutes=delta_min)
    hass.bus.async_fire(EVENT_TIME_CHANGED, {ATTR_NOW: mock_data["return_time"]})
    await hass.async_block_till_done()
    return state


async def test_sensor_availability(
    hass, caplog, pvpc_aioclient_mock: AiohttpClientMocker
):
    """Test sensor availability and handling of cloud access."""
    hass.config.time_zone = timezone("Europe/Madrid")
    config = {DOMAIN: [{CONF_NAME: "test_dst", ATTR_TARIFF: "discrimination"}]}
    mock_data = {"return_time": datetime(2019, 10, 27, 20, 0, 0, tzinfo=date_util.UTC)}

    def mock_now():
        return mock_data["return_time"]

    with patch("homeassistant.util.dt.utcnow", new=mock_now):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        caplog.clear()
        assert pvpc_aioclient_mock.call_count == 2

        await _process_time_step(hass, mock_data, "price_21h", 0.13896)
        await _process_time_step(hass, mock_data, "price_22h", 0.06893)
        assert pvpc_aioclient_mock.call_count == 4
        await _process_time_step(hass, mock_data, "price_23h", 0.06935)
        assert pvpc_aioclient_mock.call_count == 5

        # sensor has no more prices, state is "unavailable" from now on
        await _process_time_step(hass, mock_data, value="unavailable")
        await _process_time_step(hass, mock_data, value="unavailable")
        num_errors = sum(
            1 for x in caplog.get_records("call") if x.levelno == logging.ERROR
        )
        num_warnings = sum(
            1 for x in caplog.get_records("call") if x.levelno == logging.WARNING
        )
        assert num_warnings == 1
        assert num_errors == 0
        assert pvpc_aioclient_mock.call_count == 9

        # check that it is silent until it becomes available again
        caplog.clear()
        with caplog.at_level(logging.WARNING):
            # silent mode
            for _ in range(21):
                await _process_time_step(hass, mock_data, value="unavailable")
            assert pvpc_aioclient_mock.call_count == 30
            assert len(caplog.messages) == 0

            # warning about data access recovered
            await _process_time_step(hass, mock_data, value="unavailable")
            assert pvpc_aioclient_mock.call_count == 31
            assert len(caplog.messages) == 1
            assert caplog.records[0].levelno == logging.WARNING

            # working ok again
            await _process_time_step(hass, mock_data, "price_00h", value=0.06821)
            assert pvpc_aioclient_mock.call_count == 32
            await _process_time_step(hass, mock_data, "price_01h", value=0.06627)
            assert pvpc_aioclient_mock.call_count == 33
            assert len(caplog.messages) == 1
            assert caplog.records[0].levelno == logging.WARNING
