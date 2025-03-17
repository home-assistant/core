"""Tests for the buienradar component."""

from http import HTTPStatus

from buienradar.urls import JSON_FEED_URL, json_precipitation_forecast_url

from homeassistant.components.buienradar.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

TEST_CFG_DATA = {CONF_LATITUDE: 51.5288504, CONF_LONGITUDE: 5.4002156}


async def test_load_unload(
    aioclient_mock: AiohttpClientMocker, hass: HomeAssistant
) -> None:
    """Test options flow."""
    aioclient_mock.get(
        JSON_FEED_URL,
        status=HTTPStatus.OK,
        text=load_fixture("buienradar.json", DOMAIN),
    )
    aioclient_mock.get(
        json_precipitation_forecast_url(
            TEST_CFG_DATA[CONF_LATITUDE], TEST_CFG_DATA[CONF_LONGITUDE]
        ),
        status=HTTPStatus.OK,
        text=load_fixture("raindata.txt", DOMAIN),
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_LATITUDE: TEST_CFG_DATA[CONF_LATITUDE],
            CONF_LONGITUDE: TEST_CFG_DATA[CONF_LONGITUDE],
        },
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
