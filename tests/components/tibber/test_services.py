"""Test service for Tibber integration."""

import datetime as dt
from unittest.mock import MagicMock

import pytest

from homeassistant.components.tibber.const import DOMAIN
from homeassistant.components.tibber.services import PRICE_SERVICE_NAME, __get_prices
from homeassistant.core import ServiceCall
from homeassistant.exceptions import ServiceValidationError


def generate_mock_home_data():
    """Create mock data from the tibber connection."""
    mock_homes = [
        MagicMock(
            name="first_home",
            info={
                "viewer": {
                    "home": {
                        "currentSubscription": {
                            "priceInfo": {
                                "today": [
                                    {
                                        "startsAt": "2024-05-17T03:00:00.000+02:00",
                                        "total": 0.46914,
                                        "level": "VERY_EXPENSIVE",
                                    },
                                    {
                                        "startsAt": "2024-05-17T04:00:00.000+02:00",
                                        "total": 0.46914,
                                        "level": "VERY_EXPENSIVE",
                                    },
                                ],
                                "tomorrow": [
                                    {
                                        "startsAt": "2024-05-18T03:00:00.000+02:00",
                                        "total": 0.46914,
                                        "level": "VERY_EXPENSIVE",
                                    },
                                    {
                                        "startsAt": "2024-05-18T04:00:00.000+02:00",
                                        "total": 0.46914,
                                        "level": "VERY_EXPENSIVE",
                                    },
                                ],
                            }
                        }
                    }
                }
            },
        ),
        MagicMock(
            name="second_home",
            info={
                "viewer": {
                    "home": {
                        "currentSubscription": {
                            "priceInfo": {
                                "today": [
                                    {
                                        "startsAt": "2024-05-17T03:00:00.000+02:00",
                                        "total": 0.46914,
                                        "level": "VERY_EXPENSIVE",
                                    },
                                    {
                                        "startsAt": "2024-05-17T04:00:00.000+02:00",
                                        "total": 0.46914,
                                        "level": "VERY_EXPENSIVE",
                                    },
                                ],
                                "tomorrow": [
                                    {
                                        "startsAt": "2024-05-18T03:00:00.000+02:00",
                                        "total": 0.46914,
                                        "level": "VERY_EXPENSIVE",
                                    },
                                    {
                                        "startsAt": "2024-05-18T04:00:00.000+02:00",
                                        "total": 0.46914,
                                        "level": "VERY_EXPENSIVE",
                                    },
                                ],
                            }
                        }
                    }
                }
            },
        ),
    ]
    mock_homes[0].name = "first_home"
    mock_homes[1].name = "second_home"
    return mock_homes


def create_mock_tibber_connection():
    """Create a mock tibber connection."""
    tibber_connection = MagicMock()
    tibber_connection.get_homes.return_value = generate_mock_home_data()
    return tibber_connection


def create_mock_hass():
    """Create a mock hass object."""
    mock_hass = MagicMock
    mock_hass.data = {"tibber": create_mock_tibber_connection()}
    return mock_hass


async def test_get_prices():
    """Test __get_prices with mock data."""

    call = ServiceCall(
        DOMAIN, PRICE_SERVICE_NAME, {"start": "2024-05-17", "end": "2024-05-18"}
    )

    result = await __get_prices(call, hass=create_mock_hass())

    assert result == {
        "prices": {
            "first_home": [
                {
                    "start_time": dt.datetime.fromisoformat(
                        "2024-05-17 03:00:00+02:00"
                    ),
                    "price": 0.46914,
                    "level": "VERY_EXPENSIVE",
                },
                {
                    "start_time": dt.datetime.fromisoformat(
                        "2024-05-17 04:00:00+02:00"
                    ),
                    "price": 0.46914,
                    "level": "VERY_EXPENSIVE",
                },
            ],
            "second_home": [
                {
                    "start_time": dt.datetime.fromisoformat(
                        "2024-05-17 03:00:00+02:00"
                    ),
                    "price": 0.46914,
                    "level": "VERY_EXPENSIVE",
                },
                {
                    "start_time": dt.datetime.fromisoformat(
                        "2024-05-17 04:00:00+02:00"
                    ),
                    "price": 0.46914,
                    "level": "VERY_EXPENSIVE",
                },
            ],
        }
    }


async def test_get_prices_no_input():
    """Test __get_prices with no input."""

    call = ServiceCall(DOMAIN, PRICE_SERVICE_NAME, {})

    result = await __get_prices(call, hass=create_mock_hass())

    assert result == {
        "prices": {
            "first_home": [
                {
                    "start_time": dt.datetime.fromisoformat(
                        "2024-05-17 03:00:00+02:00"
                    ),
                    "price": 0.46914,
                    "level": "VERY_EXPENSIVE",
                },
                {
                    "start_time": dt.datetime.fromisoformat(
                        "2024-05-17 04:00:00+02:00"
                    ),
                    "price": 0.46914,
                    "level": "VERY_EXPENSIVE",
                },
            ],
            "second_home": [
                {
                    "start_time": dt.datetime.fromisoformat(
                        "2024-05-17 03:00:00+02:00"
                    ),
                    "price": 0.46914,
                    "level": "VERY_EXPENSIVE",
                },
                {
                    "start_time": dt.datetime.fromisoformat(
                        "2024-05-17 04:00:00+02:00"
                    ),
                    "price": 0.46914,
                    "level": "VERY_EXPENSIVE",
                },
            ],
        }
    }


async def test_get_prices_start_tomorrow():
    """Test __get_prices with start date tomorrow."""

    call = ServiceCall(DOMAIN, PRICE_SERVICE_NAME, {"start": "2024-05-18"})

    result = await __get_prices(call, hass=create_mock_hass())

    assert result == {
        "prices": {
            "first_home": [
                {
                    "start_time": dt.datetime.fromisoformat(
                        "2024-05-18 03:00:00+02:00"
                    ),
                    "price": 0.46914,
                    "level": "VERY_EXPENSIVE",
                },
                {
                    "start_time": dt.datetime.fromisoformat(
                        "2024-05-18 04:00:00+02:00"
                    ),
                    "price": 0.46914,
                    "level": "VERY_EXPENSIVE",
                },
            ],
            "second_home": [
                {
                    "start_time": dt.datetime.fromisoformat(
                        "2024-05-18 03:00:00+02:00"
                    ),
                    "price": 0.46914,
                    "level": "VERY_EXPENSIVE",
                },
                {
                    "start_time": dt.datetime.fromisoformat(
                        "2024-05-18 04:00:00+02:00"
                    ),
                    "price": 0.46914,
                    "level": "VERY_EXPENSIVE",
                },
            ],
        }
    }


async def test_get_prices_invalid_input():
    """Test __get_prices with invalid input."""

    with pytest.raises(ServiceValidationError) as excinfo:
        call = ServiceCall(DOMAIN, PRICE_SERVICE_NAME, {"start": "test"})
        await __get_prices(call, hass=create_mock_hass())

        assert "Invalid datetime provided." in str(excinfo.value)
