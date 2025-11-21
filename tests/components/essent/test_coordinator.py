"""Test the Essent coordinator."""

from __future__ import annotations

import pytest

from homeassistant.components.essent.const import API_ENDPOINT
from homeassistant.components.essent.coordinator import EssentDataUpdateCoordinator
from homeassistant.const import UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

pytestmark = [
    pytest.mark.freeze_time("2025-11-16 12:00:00+01:00"),
    pytest.mark.usefixtures("disable_coordinator_schedules"),
]


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


async def test_coordinator_fetch_failure(hass: HomeAssistant, aioclient_mock) -> None:
    """Test failed data fetch."""
    aioclient_mock.get(API_ENDPOINT, status=500)
    coordinator = EssentDataUpdateCoordinator(hass)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_invalid_json(hass: HomeAssistant, aioclient_mock) -> None:
    """Test invalid JSON response."""
    aioclient_mock.get(API_ENDPOINT, text="not json", status=200)
    coordinator = EssentDataUpdateCoordinator(hass)

    with pytest.raises(UpdateFailed, match="Invalid JSON received"):
        await coordinator._async_update_data()


async def test_coordinator_no_prices(hass: HomeAssistant, aioclient_mock) -> None:
    """Test response with no price data."""
    aioclient_mock.get(API_ENDPOINT, json={"prices": []})
    coordinator = EssentDataUpdateCoordinator(hass)

    with pytest.raises(UpdateFailed, match="No price data available"):
        await coordinator._async_update_data()


async def test_coordinator_no_tariffs(hass: HomeAssistant, aioclient_mock) -> None:
    """Test response with no tariffs."""
    aioclient_mock.get(
        API_ENDPOINT,
        json={
            "prices": [
                {
                    "date": "2025-11-16",
                    "electricity": {"tariffs": []},  # Empty tariffs
                    "gas": {"tariffs": [{"totalAmount": 0.82}]},
                }
            ]
        },
    )
    coordinator = EssentDataUpdateCoordinator(hass)

    with pytest.raises(UpdateFailed, match="No tariffs found for electricity"):
        await coordinator._async_update_data()


async def test_coordinator_no_amounts(hass: HomeAssistant, aioclient_mock) -> None:
    """Test response with tariffs but no usable amounts."""
    aioclient_mock.get(
        API_ENDPOINT,
        json={
            "prices": [
                {
                    "date": "2025-11-16",
                    "electricity": {
                        "tariffs": [
                            {"startDateTime": "2025-11-16T00:00:00"}
                        ]  # No totalAmount
                    },
                    "gas": {"tariffs": [{"totalAmount": 0.82}]},
                }
            ]
        },
    )
    coordinator = EssentDataUpdateCoordinator(hass)

    with pytest.raises(UpdateFailed, match="No usable tariff values for electricity"):
        await coordinator._async_update_data()


async def test_coordinator_no_unit(hass: HomeAssistant, aioclient_mock) -> None:
    """Test response with no unit information."""
    aioclient_mock.get(
        API_ENDPOINT,
        json={
            "prices": [
                {
                    "date": "2025-11-16",
                    "electricity": {
                        "tariffs": [{"totalAmount": 0.25}],
                        # No unit or unitOfMeasurement
                    },
                    "gas": {"tariffs": [{"totalAmount": 0.82}], "unit": "m³"},
                }
            ]
        },
    )
    coordinator = EssentDataUpdateCoordinator(hass)

    with pytest.raises(UpdateFailed, match="No unit provided for electricity"):
        await coordinator._async_update_data()


async def test_coordinator_normalize_unit_fallback(
    hass: HomeAssistant, aioclient_mock
) -> None:
    """Test unit normalization fallback for unknown units."""
    aioclient_mock.get(
        API_ENDPOINT,
        json={
            "prices": [
                {
                    "date": "2025-11-16",
                    "electricity": {
                        "tariffs": [{"totalAmount": 0.25}],
                        "unit": "unknown_unit",  # Unknown unit
                    },
                    "gas": {"tariffs": [{"totalAmount": 0.82}], "unit": "m³"},
                }
            ]
        },
    )
    coordinator = EssentDataUpdateCoordinator(hass)

    data = await coordinator._async_update_data()

    # Should keep the unknown unit as-is
    assert data["electricity"]["unit"] == "unknown_unit"
