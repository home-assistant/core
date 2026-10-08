"""Tests for the WorldTidesInfo sensor."""

from datetime import timedelta
import logging

from freezegun.api import FrozenDateTimeFactory
import pytest
import requests
import requests_mock

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.setup import async_setup_component

from tests.common import async_fire_time_changed

API_KEY = "0123-secret-api-key"
URL = "https://www.worldtides.info/api"
ENTITY_ID = "sensor.worldtidesinfo"
CONFIG = {"sensor": {"platform": "worldtidesinfo", "api_key": API_KEY}}
DATA = {
    "extremes": [
        {
            "dt": 1790650000,
            "date": "2026-09-29T10:06+0000",
            "height": -0.8,
            "type": "Low",
        },
        {
            "dt": 1790672000,
            "date": "2026-09-29T16:13+0000",
            "height": 1.1,
            "type": "High",
        },
    ]
}


async def test_setup_retries_when_api_unreachable(
    hass: HomeAssistant,
    requests_mock: requests_mock.Mocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the platform retries its setup until the API answers."""
    requests_mock.get(URL, exc=requests.exceptions.ConnectionError)
    assert await async_setup_component(hass, "sensor", CONFIG)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID) is None

    requests_mock.get(URL, json=DATA)
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state.startswith("Low tide at ")
    assert state.attributes["high_tide_height"] == 1.1


async def test_update_failure_keeps_state(
    hass: HomeAssistant,
    requests_mock: requests_mock.Mocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failed update keeps the state and does not log the API key."""
    requests_mock.get(URL, json=DATA)
    assert await async_setup_component(hass, "sensor", CONFIG)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID).state

    requests_mock.get(
        URL, exc=requests.exceptions.ConnectTimeout(f"{URL}?key={API_KEY}")
    )
    await async_update_entity(hass, ENTITY_ID)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == state
    assert "Error retrieving data from WorldTidesInfo: ConnectTimeout" in caplog.text
    assert not any(
        API_KEY in record.getMessage()
        for record in caplog.records
        if record.levelno >= logging.WARNING
    )
