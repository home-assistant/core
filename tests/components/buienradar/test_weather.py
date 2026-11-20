"""The tests for the buienradar weather component."""

from http import HTTPStatus

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.buienradar.const import DOMAIN
from homeassistant.components.weather import (
    DOMAIN as WEATHER_DOMAIN,
    SERVICE_GET_FORECASTS,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import TEST_CFG_DATA, setup_integration

WEATHER_ENTITY = "weather.buienradar"


async def test_smoke_test_setup_component(
    aioclient_mock: AiohttpClientMocker, hass: HomeAssistant
) -> None:
    """Smoke test for successfully set-up with default config."""
    aioclient_mock.get(
        "https://data.buienradar.nl/2.0/feed/json", status=HTTPStatus.NOT_FOUND
    )
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id="TEST_ID", data=TEST_CFG_DATA)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.buienradar")
    assert state.state == "unknown"


@pytest.mark.usefixtures("mock_buienradar_data")
async def test_weather(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test the weather entity state."""
    await setup_integration(hass)

    assert hass.states.get(WEATHER_ENTITY) == snapshot


@pytest.mark.usefixtures("mock_buienradar_data")
async def test_forecast(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test the daily forecast."""
    await setup_integration(hass)

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {ATTR_ENTITY_ID: WEATHER_ENTITY, "type": "daily"},
        blocking=True,
        return_response=True,
    )

    assert response == snapshot
