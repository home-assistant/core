"""Test service for Tibber integration."""

import datetime as dt
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.tibber.const import DOMAIN
from homeassistant.components.tibber.services import PRICE_SERVICE_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

START_TIME = dt.datetime.fromtimestamp(1615766400).replace(tzinfo=dt.UTC)


def generate_mock_home_data():
    """Create mock data from the tibber connection."""
    tomorrow = START_TIME + dt.timedelta(days=1)
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
                                        "startsAt": START_TIME.isoformat(),
                                        "total": 0.36914,
                                        "level": "VERY_EXPENSIVE",
                                    },
                                    {
                                        "startsAt": (
                                            START_TIME + dt.timedelta(hours=1)
                                        ).isoformat(),
                                        "total": 0.36914,
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
                                        "startsAt": START_TIME.isoformat(),
                                        "total": 0.36914,
                                        "level": "VERY_EXPENSIVE",
                                    },
                                    {
                                        "startsAt": (
                                            START_TIME + dt.timedelta(hours=1)
                                        ).isoformat(),
                                        "total": 0.36914,
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
    # set name again, as the name is special in mock objects
    # see documentation: https://docs.python.org/3/library/unittest.mock.html#mock-names-and-the-name-attribute
    mock_homes[0].name = "first_home"
    mock_homes[1].name = "second_home"
    return mock_homes


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"start": START_TIME.isoformat()},
        {
            "start": START_TIME.isoformat(),
            "end": (START_TIME + dt.timedelta(days=1)).isoformat(),
        },
    ],
)
async def test_get_prices(
    mock_tibber_setup: MagicMock,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    data,
) -> None:
    """Test get_prices with mock data."""
    freezer.move_to(START_TIME)
    mock_tibber_setup.get_homes.return_value = generate_mock_home_data()

    result = await hass.services.async_call(
        DOMAIN, PRICE_SERVICE_NAME, data, blocking=True, return_response=True
    )
    await hass.async_block_till_done()

    assert result == {
        "prices": {
            "first_home": [
                {
                    "start_time": dt.datetime.fromisoformat(START_TIME.isoformat()),
                    # back and forth conversion to deal with HAFakeDatetime vs real datetime being different types
                    "price": 0.36914,
                    "level": "VERY_EXPENSIVE",
                },
                {
                    "start_time": dt.datetime.fromisoformat(
                        (START_TIME + dt.timedelta(hours=1)).isoformat()
                    ),
                    "price": 0.36914,
                    "level": "VERY_EXPENSIVE",
                },
            ],
            "second_home": [
                {
                    "start_time": dt.datetime.fromisoformat(START_TIME.isoformat()),
                    "price": 0.36914,
                    "level": "VERY_EXPENSIVE",
                },
                {
                    "start_time": dt.datetime.fromisoformat(
                        (START_TIME + dt.timedelta(hours=1)).isoformat()
                    ),
                    "price": 0.36914,
                    "level": "VERY_EXPENSIVE",
                },
            ],
        }
    }


async def test_get_prices_start_tomorrow(
    mock_tibber_setup: MagicMock,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test get_prices with start date tomorrow."""
    freezer.move_to(START_TIME)
    tomorrow = START_TIME + dt.timedelta(days=1)

    mock_tibber_setup.get_homes.return_value = generate_mock_home_data()

    result = await hass.services.async_call(
        DOMAIN,
        PRICE_SERVICE_NAME,
        {"start": tomorrow.isoformat()},
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()

    assert result == {
        "prices": {
            "first_home": [
                {
                    "start_time": tomorrow,
                    "price": 0.46914,
                    "level": "VERY_EXPENSIVE",
                },
                {
                    "start_time": (tomorrow + dt.timedelta(hours=1)),
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
                    "start_time": (tomorrow + dt.timedelta(hours=1)),
                    "price": 0.46914,
                    "level": "VERY_EXPENSIVE",
                },
            ],
        }
    }


@pytest.mark.parametrize(
    "start_time",
    [
        START_TIME.isoformat(),
        (START_TIME + dt.timedelta(hours=4))
        .replace(tzinfo=dt.timezone(dt.timedelta(hours=4)))
        .isoformat(),
    ],
)
async def test_get_prices_with_timezones(
    mock_tibber_setup: MagicMock,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    start_time: str,
) -> None:
    """Test get_prices with timezone and without."""
    freezer.move_to(START_TIME)

    mock_tibber_setup.get_homes.return_value = generate_mock_home_data()

    result = await hass.services.async_call(
        DOMAIN,
        PRICE_SERVICE_NAME,
        {"start": start_time},
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()

    assert result == {
        "prices": {
            "first_home": [
                {
                    "start_time": START_TIME,
                    "price": 0.36914,
                    "level": "VERY_EXPENSIVE",
                },
                {
                    "start_time": START_TIME + dt.timedelta(hours=1),
                    "price": 0.36914,
                    "level": "VERY_EXPENSIVE",
                },
            ],
            "second_home": [
                {
                    "start_time": START_TIME,
                    "price": 0.36914,
                    "level": "VERY_EXPENSIVE",
                },
                {
                    "start_time": START_TIME + dt.timedelta(hours=1),
                    "price": 0.36914,
                    "level": "VERY_EXPENSIVE",
                },
            ],
        }
    }


@pytest.mark.parametrize(
    "start_time",
    [
        (START_TIME + dt.timedelta(hours=2)).isoformat(),
        (START_TIME + dt.timedelta(hours=2))
        .astimezone(tz=dt.timezone(dt.timedelta(hours=5)))
        .isoformat(),
        (START_TIME + dt.timedelta(hours=2))
        .astimezone(tz=dt.timezone(dt.timedelta(hours=8)))
        .isoformat(),
        (START_TIME + dt.timedelta(hours=2))
        .astimezone(tz=dt.timezone(dt.timedelta(hours=-8)))
        .isoformat(),
    ],
)
async def test_get_prices_with_wrong_timezones(
    mock_tibber_setup: MagicMock,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    start_time: str,
) -> None:
    """Test get_prices with incorrect time and/or timezone. We expect an empty list."""
    freezer.move_to(START_TIME)
    tomorrow = START_TIME + dt.timedelta(days=1)

    mock_tibber_setup.get_homes.return_value = generate_mock_home_data()

    result = await hass.services.async_call(
        DOMAIN,
        PRICE_SERVICE_NAME,
        {"start": start_time, "end": tomorrow.isoformat()},
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()

    assert result == {"prices": {"first_home": [], "second_home": []}}


async def test_get_prices_invalid_input(
    mock_tibber_setup: MagicMock,
    hass: HomeAssistant,
) -> None:
    """Test get_prices with invalid input."""

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            PRICE_SERVICE_NAME,
            {"start": "test"},
            blocking=True,
            return_response=True,
        )
