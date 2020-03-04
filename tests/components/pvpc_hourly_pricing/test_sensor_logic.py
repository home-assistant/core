"""Tests for the pvpc_hourly_pricing component."""
from datetime import datetime, timedelta
import json
import logging
from unittest.mock import patch

import pytest
from pytz import timezone

from homeassistant.components.pvpc_hourly_pricing import ATTR_TARIFF, DOMAIN
from homeassistant.components.pvpc_hourly_pricing.sensor import (
    extract_prices_for_tariff,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import ATTR_NOW, EVENT_TIME_CHANGED

from . import (
    FIXTURE_JSON_DATA_2019_03_30,
    FIXTURE_JSON_DATA_2019_03_31,
    FIXTURE_JSON_DATA_2019_10_26,
    FIXTURE_JSON_DATA_2019_10_27,
    FIXTURE_JSON_DATA_2019_10_29,
    check_valid_state,
)

from tests.common import async_setup_component, date_util, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture
def pvpc_aioclient_mock(aioclient_mock: AiohttpClientMocker):
    """Create a mock config entry."""
    aioclient_mock.get(
        "https://api.esios.ree.es/archives/70/download_json?locale=es&date=2019-03-30",
        text=load_fixture(f"{DOMAIN}/{FIXTURE_JSON_DATA_2019_03_30}"),
    )
    aioclient_mock.get(
        "https://api.esios.ree.es/archives/70/download_json?locale=es&date=2019-03-31",
        text=load_fixture(f"{DOMAIN}/{FIXTURE_JSON_DATA_2019_03_31}"),
    )
    aioclient_mock.get(
        "https://api.esios.ree.es/archives/70/download_json?locale=es&date=2019-10-26",
        text=load_fixture(f"{DOMAIN}/{FIXTURE_JSON_DATA_2019_10_26}"),
    )
    aioclient_mock.get(
        "https://api.esios.ree.es/archives/70/download_json?locale=es&date=2019-10-27",
        text=load_fixture(f"{DOMAIN}/{FIXTURE_JSON_DATA_2019_10_27}"),
    )

    # missing day
    aioclient_mock.get(
        "https://api.esios.ree.es/archives/70/download_json?locale=es&date=2019-10-28",
        text='{"message":"No values for specified archive"}',
    )
    aioclient_mock.get(
        "https://api.esios.ree.es/archives/70/download_json?locale=es&date=2019-10-29",
        text=load_fixture(f"{DOMAIN}/{FIXTURE_JSON_DATA_2019_10_29}"),
    )

    return aioclient_mock


@pytest.mark.parametrize(
    "fixture_name, number_of_prices",
    (
        (FIXTURE_JSON_DATA_2019_10_26, 24),
        (FIXTURE_JSON_DATA_2019_10_27, 25),
        (FIXTURE_JSON_DATA_2019_03_31, 23),
    ),
)
def test_json_parsing_logic(fixture_name, number_of_prices):
    """Test data parsing of official API files."""
    data = json.loads(load_fixture(f"{DOMAIN}/{fixture_name}"))
    prices = extract_prices_for_tariff(data["PVPC"], tariff="discrimination")
    assert len(prices) == number_of_prices


async def _process_time_step(
    hass, mock_data, key_state=None, value=None, delta_hours=1, tariff="discriminacion"
):
    state = hass.states.get("sensor.test_dst")
    check_valid_state(state, tariff=tariff, value=value, key_attr=key_state)

    mock_data["return_time"] += timedelta(hours=delta_hours)
    hass.bus.async_fire(EVENT_TIME_CHANGED, {ATTR_NOW: mock_data["return_time"]})
    await hass.async_block_till_done()
    return state


async def test_dst_spring_change(hass, pvpc_aioclient_mock: AiohttpClientMocker):
    """Test price sensor behavior in DST change day with 23 local hours."""
    hass.config.time_zone = timezone("Europe/Madrid")
    config = {DOMAIN: [{CONF_NAME: "test_dst", ATTR_TARIFF: "discriminacion"}]}
    mock_data = {"return_time": datetime(2019, 3, 30, 22, 0, tzinfo=date_util.UTC)}

    def mock_now():
        return mock_data["return_time"]

    with patch("homeassistant.util.dt.utcnow", new=mock_now):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

        state = await _process_time_step(hass, mock_data, "price_23h", 0.07022)
        assert "price_02h" in state.attributes

        state = await _process_time_step(hass, mock_data, "price_00h", 0.07328)
        assert abs(state.attributes["price_01h"] - 0.07151) < 1e-6
        assert "price_02h" not in state.attributes  # that hour doesn't exist :)
        assert abs(state.attributes["price_03h"] - 0.0671) < 1e-6

    assert pvpc_aioclient_mock.call_count == 3


async def test_dst_autumn_change(hass, pvpc_aioclient_mock: AiohttpClientMocker):
    """Test price sensor behavior in DST change day with 25 local hours."""
    hass.config.time_zone = timezone("Europe/Madrid")
    config = {DOMAIN: [{CONF_NAME: "test_dst", ATTR_TARIFF: "discriminacion"}]}
    mock_data = {"return_time": datetime(2019, 10, 26, 22, 0, 0, tzinfo=date_util.UTC)}

    def mock_now():
        return mock_data["return_time"]

    with patch("homeassistant.util.dt.utcnow", new=mock_now):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

        state = await _process_time_step(hass, mock_data, "price_00h", 0.06595)
        assert abs(state.attributes["price_01h"] - 0.0606) < 1e-6
        assert abs(state.attributes["price_02h"] - 0.05938) < 1e-6
        assert abs(state.attributes["price_02h_d"] - 0.05931) < 1e-6
        assert abs(state.attributes["price_03h"] - 0.05816) < 1e-6

    assert pvpc_aioclient_mock.call_count == 1


async def test_availability(hass, caplog, pvpc_aioclient_mock: AiohttpClientMocker):
    """Test sensor availability and handling of cloud access."""
    hass.config.time_zone = timezone("Europe/Madrid")
    config = {DOMAIN: [{CONF_NAME: "test_dst", ATTR_TARIFF: "discriminacion"}]}
    mock_data = {"return_time": datetime(2019, 10, 27, 20, 0, 0, tzinfo=date_util.UTC)}

    def mock_now():
        return mock_data["return_time"]

    with patch("homeassistant.util.dt.utcnow", new=mock_now):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        caplog.clear()
        assert pvpc_aioclient_mock.call_count == 2

        await _process_time_step(hass, mock_data, "price_21h")
        await _process_time_step(hass, mock_data, "price_22h", 0.06893)
        assert pvpc_aioclient_mock.call_count == 4
        await _process_time_step(hass, mock_data, "price_23h", 0.06935)
        assert pvpc_aioclient_mock.call_count == 6

        # sensor has no more prices, state is "unavailable" from now on
        await _process_time_step(hass, mock_data, value="unavailable")
        num_errors = sum(
            1 for x in caplog.get_records("call") if x.levelno == logging.ERROR
        )
        num_warnings = sum(
            1 for x in caplog.get_records("call") if x.levelno == logging.WARNING
        )
        assert num_warnings == 4
        assert num_errors == 1
        assert pvpc_aioclient_mock.call_count == 8

        # check that it is silent until it becomes available again
        caplog.clear()
        with caplog.at_level(logging.WARNING):
            # silent mode
            for _ in range(22):
                await _process_time_step(hass, mock_data, value="unavailable")
            assert pvpc_aioclient_mock.call_count == 52
            assert len(caplog.messages) == 0

            # warning about data access recovered
            await _process_time_step(hass, mock_data, value="unavailable")
            assert pvpc_aioclient_mock.call_count == 54
            assert len(caplog.messages) == 1
            assert caplog.records[0].levelno == logging.WARNING

            # working ok again
            await _process_time_step(hass, mock_data, "price_00h", value=0.06821)
            assert pvpc_aioclient_mock.call_count == 55
            await _process_time_step(hass, mock_data, "price_01h", value=0.06627)
            assert pvpc_aioclient_mock.call_count == 56
            assert len(caplog.messages) == 1
            assert caplog.records[0].levelno == logging.WARNING
