"""Tests for the Environment Canada services."""

from typing import Any

import probatio
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.environment_canada.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import init_integration

SERVICE_GET_ALERTS = "get_alerts"
SERVICE_GET_PRECIPITATION_FORECAST = "get_precipitation_forecast"


async def test_get_alerts(
    hass: HomeAssistant, snapshot: SnapshotAssertion, ec_data: dict[str, Any]
) -> None:
    """Test the get_alerts service returns active alerts."""
    config_entry = await init_integration(hass, ec_data)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_ALERTS,
        {"config_entry_id": config_entry.entry_id},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


async def test_get_alerts_not_connected(
    hass: HomeAssistant, ec_data: dict[str, Any]
) -> None:
    """Test get_alerts raises when weather data is not connected."""
    config_entry = await init_integration(hass, ec_data)
    config_entry.runtime_data.weather_coordinator.ec_data = None

    with pytest.raises(HomeAssistantError, match="not connected"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_ALERTS,
            {"config_entry_id": config_entry.entry_id},
            blocking=True,
            return_response=True,
        )


async def test_get_precipitation_forecast(
    hass: HomeAssistant, snapshot: SnapshotAssertion, ec_data: dict[str, Any]
) -> None:
    """Test the get_precipitation_forecast service returns the series."""
    config_entry = await init_integration(hass, ec_data)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_PRECIPITATION_FORECAST,
        {"config_entry_id": config_entry.entry_id},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot
    config_entry.runtime_data.precip_forecast.update.assert_awaited_once()


async def test_get_precipitation_forecast_options(
    hass: HomeAssistant, ec_data: dict[str, Any]
) -> None:
    """Test the get_precipitation_forecast service applies requested options."""
    config_entry = await init_integration(hass, ec_data)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_PRECIPITATION_FORECAST,
        {
            "config_entry_id": config_entry.entry_id,
            "precip_type": "snow",
            "past_minutes": 30,
            "future_minutes": 15,
            "hourly_hours": 6,
        },
        blocking=True,
        return_response=True,
    )

    precip = config_entry.runtime_data.precip_forecast
    assert precip.precip_type == "snow"
    assert precip.past_minutes == 30
    assert precip.future_minutes == 15
    assert precip.hourly_hours == 6


async def test_get_precipitation_forecast_invalid_option(
    hass: HomeAssistant, ec_data: dict[str, Any]
) -> None:
    """Test the get_precipitation_forecast service rejects out-of-range options."""
    config_entry = await init_integration(hass, ec_data)

    with pytest.raises(probatio.MultipleInvalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_PRECIPITATION_FORECAST,
            {"config_entry_id": config_entry.entry_id, "hourly_hours": 100},
            blocking=True,
            return_response=True,
        )
