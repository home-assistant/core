"""Test weather."""

import copy
from typing import Any

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.weather import (
    DOMAIN as WEATHER_DOMAIN,
    SERVICE_GET_FORECASTS,
)
from homeassistant.core import HomeAssistant

from . import init_integration


async def test_forecast_daily(
    hass: HomeAssistant, snapshot: SnapshotAssertion, ec_data: dict[str, Any]
) -> None:
    """Test basic forecast."""

    # First entry in test data is a half day; we don't want that for this test
    local_ec_data = copy.deepcopy(ec_data)
    del local_ec_data["daily_forecasts"][0]

    await init_integration(hass, local_ec_data)

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {
            "entity_id": "weather.home_forecast",
            "type": "daily",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


async def test_forecast_daily_with_some_previous_days_data(
    hass: HomeAssistant, snapshot: SnapshotAssertion, ec_data: dict[str, Any]
) -> None:
    """Test forecast with half day at start."""

    await init_integration(hass, ec_data)

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {
            "entity_id": "weather.home_forecast",
            "type": "daily",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot
