"""Test service for Tibber integration."""

import datetime as dt
from unittest.mock import AsyncMock, MagicMock

import aiohttp
from freezegun.api import FrozenDateTimeFactory
import pytest
import tibber
from tibber.data_api import PriceDetails, PriceInterval

from homeassistant.components.tibber.const import DOMAIN
from homeassistant.components.tibber.services import TibberService
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

START_TIME = dt.datetime.fromtimestamp(1615766400).replace(tzinfo=dt.UTC)


def _mock_home(name: str) -> MagicMock:
    """Create a mock home whose Data API returns its prices in the requested range."""
    tomorrow = START_TIME + dt.timedelta(days=1)
    intervals = [
        PriceInterval(start=start, consumption=PriceDetails(price=price))
        for start, price in (
            (START_TIME, 0.36914),
            (START_TIME + dt.timedelta(hours=1), 0.36914),
            (tomorrow, 0.46914),
            (tomorrow + dt.timedelta(hours=1), 0.46914),
        )
    ]

    async def get_prices(start: dt.datetime, end: dt.datetime) -> list[PriceInterval]:
        return [interval for interval in intervals if start <= interval.start < end]

    home = MagicMock()
    # The name is special in mock objects, so it is set after creation.
    home.name = name
    home.get_prices = AsyncMock(side_effect=get_prices)
    return home


def generate_mock_home_data() -> list[MagicMock]:
    """Create mock homes from the tibber connection."""
    return [_mock_home("first_home"), _mock_home("second_home")]


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
        DOMAIN, TibberService.GET_PRICES, data, blocking=True, return_response=True
    )
    await hass.async_block_till_done()

    assert result == {
        "prices": {
            "first_home": [
                {
                    "start_time": START_TIME.isoformat(),
                    "price": 0.36914,
                },
                {
                    "start_time": (START_TIME + dt.timedelta(hours=1)).isoformat(),
                    "price": 0.36914,
                },
            ],
            "second_home": [
                {
                    "start_time": START_TIME.isoformat(),
                    "price": 0.36914,
                },
                {
                    "start_time": (START_TIME + dt.timedelta(hours=1)).isoformat(),
                    "price": 0.36914,
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
        TibberService.GET_PRICES,
        {"start": tomorrow.isoformat()},
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()

    assert result == {
        "prices": {
            "first_home": [
                {
                    "start_time": tomorrow.isoformat(),
                    "price": 0.46914,
                },
                {
                    "start_time": (tomorrow + dt.timedelta(hours=1)).isoformat(),
                    "price": 0.46914,
                },
            ],
            "second_home": [
                {
                    "start_time": tomorrow.isoformat(),
                    "price": 0.46914,
                },
                {
                    "start_time": (tomorrow + dt.timedelta(hours=1)).isoformat(),
                    "price": 0.46914,
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
        TibberService.GET_PRICES,
        {"start": start_time},
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()

    assert result == {
        "prices": {
            "first_home": [
                {
                    "start_time": START_TIME.isoformat(),
                    "price": 0.36914,
                },
                {
                    "start_time": (START_TIME + dt.timedelta(hours=1)).isoformat(),
                    "price": 0.36914,
                },
            ],
            "second_home": [
                {
                    "start_time": START_TIME.isoformat(),
                    "price": 0.36914,
                },
                {
                    "start_time": (START_TIME + dt.timedelta(hours=1)).isoformat(),
                    "price": 0.36914,
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
        TibberService.GET_PRICES,
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
            TibberService.GET_PRICES,
            {"start": "test"},
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(TimeoutError(), id="timeout"),
        pytest.param(tibber.InvalidLoginError(401), id="invalid_login"),
        pytest.param(tibber.RetryableHttpExceptionError(503), id="retryable_http"),
        pytest.param(tibber.FatalHttpExceptionError(500), id="fatal_http"),
        pytest.param(aiohttp.ClientError("connection failed"), id="client_error"),
    ],
)
async def test_get_prices_refresh_raises_handled_exception(
    mock_tibber_setup: MagicMock,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """When price refresh fails with handled exceptions, raise HomeAssistantError."""
    freezer.move_to(START_TIME)
    mock_home = MagicMock()
    mock_home.name = "home"
    mock_home.get_prices = AsyncMock(side_effect=exception)
    mock_tibber_setup.get_homes.return_value = [mock_home]

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            TibberService.GET_PRICES,
            {},
            blocking=True,
            return_response=True,
        )


async def test_get_prices_for_past_range(
    mock_tibber_setup: MagicMock,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test get_prices fetches the requested range, also in the past."""
    freezer.move_to(START_TIME + dt.timedelta(days=30))
    homes = generate_mock_home_data()
    mock_tibber_setup.get_homes.return_value = homes
    end = START_TIME + dt.timedelta(hours=1)

    result = await hass.services.async_call(
        DOMAIN,
        TibberService.GET_PRICES,
        {"start": START_TIME.isoformat(), "end": end.isoformat()},
        blocking=True,
        return_response=True,
    )

    homes[0].get_prices.assert_awaited_once_with(START_TIME, end)
    assert result == {
        "prices": {
            "first_home": [{"start_time": START_TIME.isoformat(), "price": 0.36914}],
            "second_home": [{"start_time": START_TIME.isoformat(), "price": 0.36914}],
        }
    }


async def test_get_prices_home_without_prices(
    mock_tibber_setup: MagicMock,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test get_prices returns no prices for a home the Data API has no prices for."""
    freezer.move_to(START_TIME)
    mock_home = MagicMock()
    mock_home.name = "home"
    mock_home.get_prices = AsyncMock(
        side_effect=tibber.PricesNotAvailableError(403, "No prices")
    )
    mock_tibber_setup.get_homes.return_value = [mock_home]

    result = await hass.services.async_call(
        DOMAIN,
        TibberService.GET_PRICES,
        {},
        blocking=True,
        return_response=True,
    )

    assert result == {"prices": {"home": []}}
