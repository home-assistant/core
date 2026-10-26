"""Test the boundary between Home Assistant and the released One Call 4.0 client."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, async_load_json_object_fixture
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.openweathermap.const import DOMAIN, OWM_MODE_V40
from homeassistant.components.openweathermap.services import SERVICE_GET_MINUTE_FORECAST
from homeassistant.components.weather import (
    DOMAIN as WEATHER_DOMAIN,
    SERVICE_GET_FORECASTS,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import setup_platform
from .conftest import API_KEY, LATITUDE, LONGITUDE

ENTITY_ID = "weather.openweathermap"


@pytest.mark.parametrize("mode", [OWM_MODE_V40], indirect=True)
async def test_v4_transport(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    snapshot: SnapshotAssertion,
) -> None:
    """The real client requests v4 resources and exposes all weather products."""
    responses = await async_load_json_object_fixture(hass, "v4_weather.json", DOMAIN)
    urls = [
        f"https://api.openweathermap.org/data/4.0/onecall/{endpoint}"
        f"?lat={LATITUDE}&lon={LONGITUDE}&appid={API_KEY}&units=metric&lang=en"
        for endpoint in responses
    ]
    for url, response in zip(urls, responses.values(), strict=True):
        aioclient_mock.get(url, json=response)

    with patch(
        "pyopenweathermap.http_client.ClientSession",
        side_effect=lambda: aioclient_mock.create_session(hass.loop),
    ):
        await setup_platform(
            hass, mock_config_entry, [Platform.WEATHER, Platform.SENSOR]
        )

    assert [str(call[1]) for call in aioclient_mock.mock_calls] == urls
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "cloudy"
    assert state.attributes["temperature"] == 6.8
    assert hass.states.get("sensor.openweathermap_temperature").state == "6.84"

    for forecast_type in ("hourly", "daily"):
        response = await hass.services.async_call(
            WEATHER_DOMAIN,
            SERVICE_GET_FORECASTS,
            {"entity_id": ENTITY_ID, "type": forecast_type},
            blocking=True,
            return_response=True,
        )
        assert response == snapshot(name=forecast_type)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_MINUTE_FORECAST,
        {"entity_id": ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot(name="minutely")
