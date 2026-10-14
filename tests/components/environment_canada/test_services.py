"""Tests for the Environment Canada services."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import probatio
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.environment_canada.const import DOMAIN
from homeassistant.const import CONF_LANGUAGE, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import FIXTURE_USER_INPUT, init_integration

SERVICE_GET_ALERTS = "get_alerts"
SERVICE_GET_PRECIPITATION_FORECAST = "get_precipitation_forecast"


def _precip_mock() -> MagicMock:
    """Build an ECPrecipForecast constructor mock returning sample data."""
    instance = MagicMock()
    instance.update = AsyncMock()
    instance.nowcast = [
        {
            "timestamp": datetime(2022, 10, 4, 12, 0, tzinfo=UTC),
            "rate": 1.2391,
            "unit": "mm/h",
            "label": "1.0 - 2.0 (mm/h)",
            "precip_type": "rain",
            "forecast": False,
        }
    ]
    instance.hourly = [
        {
            "timestamp": datetime(2022, 10, 4, 13, 0, tzinfo=UTC),
            "amount": 1.726,
            "probability": 57,
            "conditional_amount": 0.909,
            "expected_amount": 0.518,
            "precip_type": "Rain",
            "label": "0.5 - 1 mm",
        }
    ]
    instance.metadata = {
        "attribution": "Data provided by Environment Canada",
        "timestamp": "2022-10-04T12:00:00+00:00",
    }
    return MagicMock(return_value=instance)


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
    constructor = _precip_mock()

    with patch(
        "homeassistant.components.environment_canada.services.ECPrecipForecast",
        constructor,
    ):
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_PRECIPITATION_FORECAST,
            {"config_entry_id": config_entry.entry_id},
            blocking=True,
            return_response=True,
        )

    assert response == snapshot
    constructor.assert_called_once_with(
        coordinates=(
            FIXTURE_USER_INPUT[CONF_LATITUDE],
            FIXTURE_USER_INPUT[CONF_LONGITUDE],
        ),
        language=FIXTURE_USER_INPUT[CONF_LANGUAGE].lower(),
    )
    constructor.return_value.update.assert_awaited_once()


async def test_get_precipitation_forecast_options(
    hass: HomeAssistant, ec_data: dict[str, Any]
) -> None:
    """Test the get_precipitation_forecast service passes requested options."""
    config_entry = await init_integration(hass, ec_data)
    constructor = _precip_mock()

    with patch(
        "homeassistant.components.environment_canada.services.ECPrecipForecast",
        constructor,
    ):
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

    constructor.assert_called_once_with(
        coordinates=(
            FIXTURE_USER_INPUT[CONF_LATITUDE],
            FIXTURE_USER_INPUT[CONF_LONGITUDE],
        ),
        language=FIXTURE_USER_INPUT[CONF_LANGUAGE].lower(),
        precip_type="snow",
        past_minutes=30,
        future_minutes=15,
        hourly_hours=6,
    )


async def test_get_precipitation_forecast_options_do_not_leak(
    hass: HomeAssistant, ec_data: dict[str, Any]
) -> None:
    """Test that options from one call are not carried over to the next."""
    config_entry = await init_integration(hass, ec_data)
    constructor = _precip_mock()

    with patch(
        "homeassistant.components.environment_canada.services.ECPrecipForecast",
        constructor,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_PRECIPITATION_FORECAST,
            {"config_entry_id": config_entry.entry_id, "precip_type": "snow"},
            blocking=True,
            return_response=True,
        )
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_PRECIPITATION_FORECAST,
            {"config_entry_id": config_entry.entry_id},
            blocking=True,
            return_response=True,
        )

    assert "precip_type" not in constructor.call_args_list[1].kwargs


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
