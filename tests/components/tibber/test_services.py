"""Test service for Tibber integration."""

import asyncio
import datetime as dt
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.tibber.const import DOMAIN
from homeassistant.components.tibber.services import PRICE_SERVICE_NAME, __get_prices
from homeassistant.core import ServiceCall
from homeassistant.exceptions import ServiceValidationError

STARTTIME = dt.datetime.fromtimestamp(1615766400)


def generate_mock_home_data():
    """Create mock data from the tibber connection."""
    tomorrow = STARTTIME + dt.timedelta(days=1)
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
                                        "startsAt": STARTTIME.isoformat(),
                                        "total": 0.46914,
                                        "level": "VERY_EXPENSIVE",
                                    },
                                    {
                                        "startsAt": (
                                            STARTTIME + dt.timedelta(hours=1)
                                        ).isoformat(),
                                        "total": 0.46914,
                                        "level": "VERY_EXPENSIVE",
                                    },
                                ],
                                "tomorrow": [
                                    {
                                        "startsAt": tomorrow.isoformat(),
                                        "total": 0.46914,
                                        "level": "VERY_EXPENSIVE",
                                    },
                                    {
                                        "startsAt": (
                                            tomorrow + dt.timedelta(hours=1)
                                        ).isoformat(),
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
                                        "startsAt": STARTTIME.isoformat(),
                                        "total": 0.46914,
                                        "level": "VERY_EXPENSIVE",
                                    },
                                    {
                                        "startsAt": (
                                            STARTTIME + dt.timedelta(hours=1)
                                        ).isoformat(),
                                        "total": 0.46914,
                                        "level": "VERY_EXPENSIVE",
                                    },
                                ],
                                "tomorrow": [
                                    {
                                        "startsAt": tomorrow.isoformat(),
                                        "total": 0.46914,
                                        "level": "VERY_EXPENSIVE",
                                    },
                                    {
                                        "startsAt": (
                                            tomorrow + dt.timedelta(hours=1)
                                        ).isoformat(),
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


async def test_get_prices(
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test __get_prices with mock data."""
    freezer.move_to(STARTTIME)
    tomorrow = STARTTIME + dt.timedelta(days=1)
    call = ServiceCall(
        DOMAIN,
        PRICE_SERVICE_NAME,
        {"start": STARTTIME.date().isoformat(), "end": tomorrow.date().isoformat()},
    )

    result = await __get_prices(call, hass=create_mock_hass())

    assert result == {
        "prices": {
            "first_home": [
                {
                    "start_time": STARTTIME,
                    "price": 0.46914,
                    "level": "VERY_EXPENSIVE",
                },
                {
                    "start_time": STARTTIME + dt.timedelta(hours=1),
                    "price": 0.46914,
                    "level": "VERY_EXPENSIVE",
                },
            ],
            "second_home": [
                {
                    "start_time": STARTTIME,
                    "price": 0.46914,
                    "level": "VERY_EXPENSIVE",
                },
                {
                    "start_time": STARTTIME + dt.timedelta(hours=1),
                    "price": 0.46914,
                    "level": "VERY_EXPENSIVE",
                },
            ],
        }
    }


async def test_get_prices_no_input(
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test __get_prices with no input."""
    freezer.move_to(STARTTIME)
    call = ServiceCall(DOMAIN, PRICE_SERVICE_NAME, {})

    result = await __get_prices(call, hass=create_mock_hass())

    assert result == {
        "prices": {
            "first_home": [
                {
                    "start_time": STARTTIME,
                    "price": 0.46914,
                    "level": "VERY_EXPENSIVE",
                },
                {
                    "start_time": STARTTIME + dt.timedelta(hours=1),
                    "price": 0.46914,
                    "level": "VERY_EXPENSIVE",
                },
            ],
            "second_home": [
                {
                    "start_time": STARTTIME,
                    "price": 0.46914,
                    "level": "VERY_EXPENSIVE",
                },
                {
                    "start_time": STARTTIME + dt.timedelta(hours=1),
                    "price": 0.46914,
                    "level": "VERY_EXPENSIVE",
                },
            ],
        }
    }


async def test_get_prices_start_tomorrow(
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test __get_prices with start date tomorrow."""
    freezer.move_to(STARTTIME)
    tomorrow = STARTTIME + dt.timedelta(days=1)
    call = ServiceCall(
        DOMAIN, PRICE_SERVICE_NAME, {"start": tomorrow.date().isoformat()}
    )

    result = await __get_prices(call, hass=create_mock_hass())

    assert result == {
        "prices": {
            "first_home": [
                {
                    "start_time": tomorrow,
                    "price": 0.46914,
                    "level": "VERY_EXPENSIVE",
                },
                {
                    "start_time": tomorrow + dt.timedelta(hours=1),
                    "price": 0.46914,
                    "level": "VERY_EXPENSIVE",
                },
            ],
            "second_home": [
                {
                    "start_time": tomorrow,
                    "price": 0.46914,
                    "level": "VERY_EXPENSIVE",
                },
                {
                    "start_time": tomorrow + dt.timedelta(hours=1),
                    "price": 0.46914,
                    "level": "VERY_EXPENSIVE",
                },
            ],
        }
    }


async def test_get_prices_invalid_input() -> None:
    """Test __get_prices with invalid input."""

    call = ServiceCall(DOMAIN, PRICE_SERVICE_NAME, {"start": "test"})
    task = asyncio.create_task(__get_prices(call, hass=create_mock_hass()))

    with pytest.raises(ServiceValidationError) as excinfo:
        await task

    assert "Invalid datetime provided." in str(excinfo.value)
