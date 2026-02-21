"""Test API client for dk_fuelprices."""

from __future__ import annotations

from unittest.mock import Mock

from aiohttp import ClientResponseError
from pybraendstofpriser.exceptions import ProductNotFoundError
import pytest

from homeassistant.components.dk_fuelprices.api import APIClient
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError

from .conftest import TEST_API_KEY, TEST_COMPANY, TEST_STATION


def _client_error(status: int) -> ClientResponseError:
    """Create an aiohttp client response error with a specific status code."""
    return ClientResponseError(
        request_info=Mock(),
        history=(),
        status=status,
        message="error",
        headers=None,
    )


async def test_api_client_update_success(
    hass: HomeAssistant, mock_braendstofpriser
) -> None:
    """Test coordinator updates prices and timestamp."""
    client = APIClient(
        hass,
        TEST_API_KEY,
        TEST_COMPANY,
        TEST_STATION,
        {"Blyfri95": True, "Diesel": False},
        "station_1",
    )

    client._api.get_prices.return_value = {
        "station": {
            "id": TEST_STATION["id"],
            "name": "Updated Station",
            "last_update": "2024-01-02T13:14:15",
        },
        "prices": {"Blyfri95": 15.55},
    }

    await client._async_update_data()

    assert client.station_name == "Updated Station"
    assert client.updated_at is not None
    assert client.updated_at.isoformat() == "2024-01-02T13:14:15"
    assert client.products["Blyfri95"]["price"] == 15.55


async def test_api_client_update_last_update_none(
    hass: HomeAssistant, mock_braendstofpriser
) -> None:
    """Test coordinator handles missing timestamp."""
    client = APIClient(
        hass,
        TEST_API_KEY,
        TEST_COMPANY,
        TEST_STATION,
        {"Blyfri95": True},
        "station_1",
    )

    client._api.get_prices.return_value = {
        "station": {
            "id": TEST_STATION["id"],
            "name": TEST_STATION["name"],
            "last_update": None,
        },
        "prices": {"Blyfri95": 12.34},
    }

    await client._async_update_data()

    assert client.updated_at is None


async def test_api_client_setup_populates_products(
    hass: HomeAssistant, mock_braendstofpriser
) -> None:
    """Test _async_setup repopulates selected products."""
    client = APIClient(
        hass,
        TEST_API_KEY,
        TEST_COMPANY,
        TEST_STATION,
        {"Blyfri95": True, "Diesel": False},
        "station_1",
    )
    client.products = {}

    await client._async_setup()

    assert client.products == {"Blyfri95": {"name": "Blyfri95", "price": None}}


async def test_api_client_product_not_found_raises_entry_error(
    hass: HomeAssistant, mock_braendstofpriser
) -> None:
    """Test ProductNotFoundError is mapped to ConfigEntryError."""
    client = APIClient(
        hass,
        TEST_API_KEY,
        TEST_COMPANY,
        TEST_STATION,
        {"Blyfri95": True},
        "station_1",
    )
    client._api.get_prices.side_effect = ProductNotFoundError("missing")

    with pytest.raises(ConfigEntryError):
        await client._async_update_data()


async def test_api_client_unauthorized_raises_auth_failed(
    hass: HomeAssistant, mock_braendstofpriser
) -> None:
    """Test HTTP 401 is mapped to ConfigEntryAuthFailed."""
    client = APIClient(
        hass,
        TEST_API_KEY,
        TEST_COMPANY,
        TEST_STATION,
        {"Blyfri95": True},
        "station_1",
    )
    client._api.get_prices.side_effect = _client_error(401)

    with pytest.raises(ConfigEntryAuthFailed):
        await client._async_update_data()


async def test_api_client_other_http_error_raises_entry_error(
    hass: HomeAssistant, mock_braendstofpriser
) -> None:
    """Test non-401 HTTP errors are mapped to ConfigEntryError."""
    client = APIClient(
        hass,
        TEST_API_KEY,
        TEST_COMPANY,
        TEST_STATION,
        {"Blyfri95": True},
        "station_1",
    )
    client._api.get_prices.side_effect = _client_error(500)

    with pytest.raises(ConfigEntryError):
        await client._async_update_data()
