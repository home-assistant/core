"""Test Green Planet Energy service."""

import pytest
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceNotFound

from tests.common import MockConfigEntry


async def test_get_price_service_current(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test get_price service without hour parameter."""
    # Call service without hour parameter (should return current price)
    response = await hass.services.async_call(
        "green_planet_energy",
        "get_price",
        {},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert "hour" in response
    assert "price" in response
    assert "time_slot" in response
    assert "unit" in response
    assert response["unit"] == "€/kWh"
    assert isinstance(response["hour"], int)
    assert 0 <= response["hour"] <= 23
    assert isinstance(response["price"], float)


async def test_get_price_service_specific_hour(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test get_price service with specific hour parameter."""
    # Test hour 14 (should return 0.34 based on mock data)
    response = await hass.services.async_call(
        "green_planet_energy",
        "get_price",
        {"hour": 14},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert response["hour"] == 14
    assert response["price"] == 0.34  # Mock data: 0.20 + (14 * 0.01)
    assert response["time_slot"] == "14:00-15:00"
    assert response["unit"] == "€/kWh"


async def test_get_price_service_hour_0(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test get_price service with hour 0."""
    response = await hass.services.async_call(
        "green_planet_energy",
        "get_price",
        {"hour": 0},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert response["hour"] == 0
    assert response["price"] == 0.2  # Mock data: 0.20 + (0 * 0.01)
    assert response["time_slot"] == "00:00-01:00"
    assert response["unit"] == "€/kWh"


async def test_get_price_service_hour_23(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test get_price service with hour 23."""
    response = await hass.services.async_call(
        "green_planet_energy",
        "get_price",
        {"hour": 23},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert response["hour"] == 23
    # Use pytest.approx to handle floating point precision issues
    assert abs(response["price"] - 0.43) < 0.0001  # Mock data: 0.20 + (23 * 0.01)
    assert response["time_slot"] == "23:00-24:00"
    assert response["unit"] == "€/kWh"


async def test_get_price_service_invalid_hour(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test get_price service with invalid hour parameter."""
    # Test hour > 23 - this should be caught by voluptuous schema validation
    with pytest.raises(vol.MultipleInvalid):
        await hass.services.async_call(
            "green_planet_energy",
            "get_price",
            {"hour": 24},
            blocking=True,
            return_response=True,
        )

    # Test hour < 0 - this should be caught by voluptuous schema validation
    with pytest.raises(vol.MultipleInvalid):
        await hass.services.async_call(
            "green_planet_energy",
            "get_price",
            {"hour": -1},
            blocking=True,
            return_response=True,
        )


async def test_get_price_service_no_integration(hass: HomeAssistant) -> None:
    """Test get_price service when no integration is configured."""
    with pytest.raises(ServiceNotFound):
        await hass.services.async_call(
            "green_planet_energy",
            "get_price",
            {},
            blocking=True,
            return_response=True,
        )
