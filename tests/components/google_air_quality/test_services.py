"""Test services for Google Air Quality."""

from datetime import timedelta
import json
from unittest.mock import AsyncMock

from google_air_quality_api.model import AirQualityForecastData
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.google_air_quality.const import DOMAIN
from homeassistant.components.google_air_quality.services import (
    ATTR_HOURS,
    SERVICE_GET_FORECAST,
)
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry, async_load_fixture


@pytest.mark.usefixtures("setup_integration")
async def test_get_forecast_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test fetching a forecast for a subentry."""
    device = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, f"{mock_config_entry.entry_id}_home-subentry-id")}
    )
    assert device is not None

    forecast = AirQualityForecastData.from_dict(
        json.loads(await async_load_fixture(hass, "air_quality_forecast.json", DOMAIN))
    )
    mock_api.async_get_forecast.return_value = forecast

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_FORECAST,
        {
            ATTR_DEVICE_ID: device.id,
            ATTR_HOURS: 12,
        },
        blocking=True,
        return_response=True,
    )

    mock_api.async_get_forecast.assert_awaited_once_with(
        10.1, 20.1, timedelta(hours=12)
    )
    assert response == snapshot


@pytest.mark.usefixtures("setup_integration")
async def test_get_forecast_service_unknown_subentry(
    hass: HomeAssistant,
) -> None:
    """Test fetching a forecast for an unknown subentry."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_FORECAST,
            {
                ATTR_DEVICE_ID: "unknown-device-id",
                ATTR_HOURS: 12,
            },
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_key == "device_not_found"
