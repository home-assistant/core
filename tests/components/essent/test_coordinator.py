"""Test the Essent coordinator."""

from __future__ import annotations

import pytest

from homeassistant.components.essent.const import API_ENDPOINT
from homeassistant.components.essent.coordinator import EssentDataUpdateCoordinator
from homeassistant.const import UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

pytestmark = pytest.mark.freeze_time("2025-11-16 12:00:00+01:00")


async def test_coordinator_fetch_success(
    hass: HomeAssistant, aioclient_mock, essent_api_response: dict
) -> None:
    """Test successful data fetch."""
    aioclient_mock.get(API_ENDPOINT, json=essent_api_response)
    coordinator = EssentDataUpdateCoordinator(hass)

    data = await coordinator._async_update_data()

    assert data is not None
    assert len(data["electricity"]["tariffs"]) == 3
    assert len(data["electricity"]["tariffs_tomorrow"]) == 1
    assert len(data["gas"]["tariffs"]) == 3
    assert data["electricity"]["unit"] == UnitOfEnergy.KILO_WATT_HOUR
    assert data["gas"]["unit"] == UnitOfVolume.CUBIC_METERS
    assert data["electricity"]["min_price"] == 0.2
    assert round(data["electricity"]["avg_price"], 4) == 0.2233
    assert data["electricity"]["max_price"] == 0.25


async def test_coordinator_fetch_failure(
    hass: HomeAssistant, aioclient_mock
) -> None:
    """Test failed data fetch."""
    aioclient_mock.get(API_ENDPOINT, status=500)
    coordinator = EssentDataUpdateCoordinator(hass)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
