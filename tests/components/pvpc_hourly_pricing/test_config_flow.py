"""Tests for the pvpc_hourly_pricing config_flow."""
from datetime import datetime
from unittest.mock import patch

import pytest
from pytz import timezone

from homeassistant import data_entry_flow
from homeassistant.components.pvpc_hourly_pricing import ATTR_TARIFF, DOMAIN
from homeassistant.const import CONF_NAME

from . import FIXTURE_XML_DATA_2019_03_30, check_valid_state

from tests.common import date_util, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(name="pvpc_aioclient_mock")
def pvpc_aioclient_mock(aioclient_mock: AiohttpClientMocker):
    """Create a mock config entry."""
    aioclient_mock.get(
        "https://api.esios.ree.es/archives/80/download?date=2019-03-30",
        text=load_fixture(f"{DOMAIN}/{FIXTURE_XML_DATA_2019_03_30}"),
        headers={"Content-Type": "xml"},
    )
    return aioclient_mock


async def test_config_flow(hass, pvpc_aioclient_mock: AiohttpClientMocker):
    """
    Test config flow for pvpc_hourly_pricing.

    - Create a new entry with tariff "normal"
    - Check state and attributes
    - Use Options flow to change to tariff "coche_electrico"
    - Check new tariff state and compare both.
    - Check abort stage on name collision
    """
    hass.config.time_zone = timezone("Europe/Madrid")
    mock_data = {"return_time": datetime(2019, 3, 30, 14, 0, tzinfo=date_util.UTC)}

    def mock_now():
        return mock_data["return_time"]

    with patch("homeassistant.util.dt.utcnow", new=mock_now):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_NAME: "test", ATTR_TARIFF: "normal"}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

        await hass.async_block_till_done()
        state = hass.states.get("sensor.test")
        check_valid_state(state, tariff="normal")
        assert pvpc_aioclient_mock.call_count == 1

        # get entry and min_price with tariff 'normal' to play with options flow
        entry = result["result"]
        min_price_normal_tariff = state.attributes["min_price"]

        # Use options to change tariff
        result = await hass.config_entries.options.async_init(
            entry.entry_id, context={"source": "user"}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={ATTR_TARIFF: "coche_electrico"}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["data"][ATTR_TARIFF] == "coche_electrico"

        # check tariff change
        await hass.async_block_till_done()
        state = hass.states.get("sensor.test")
        check_valid_state(state, tariff="coche_electrico")
        assert pvpc_aioclient_mock.call_count == 2

        # Check parsing was ok by ensuring that EV is better tariff than default one
        min_price_electric_car_tariff = state.attributes["min_price"]
        assert min_price_electric_car_tariff < min_price_normal_tariff

        # Check abort when configuring another with same name
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_NAME: "test", ATTR_TARIFF: "normal"}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT

        assert pvpc_aioclient_mock.call_count == 2
