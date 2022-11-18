"""Test common."""
import datetime as dt
from unittest.mock import AsyncMock, MagicMock

CONSUMPTION_DATA_1 = [
    {
        "from": "2022-01-03T00:00:00.000+01:00",
        "totalCost": 1.1,
        "consumption": 2.1,
    },
    {
        "from": "2022-01-03T01:00:00.000+01:00",
        "totalCost": 1.2,
        "consumption": 2.2,
    },
    {
        "from": "2022-01-03T02:00:00.000+01:00",
        "totalCost": 1.3,
        "consumption": 2.3,
    },
]

PRODUCTION_DATA_1 = [
    {
        "from": "2022-01-03T00:00:00.000+01:00",
        "profit": 0.1,
        "production": 3.1,
    },
    {
        "from": "2022-01-03T01:00:00.000+01:00",
        "profit": 0.2,
        "production": 3.2,
    },
    {
        "from": "2022-01-03T02:00:00.000+01:00",
        "profit": 0.3,
        "production": 3.3,
    },
]


def mock_get_homes(only_active=True):
    """Return a list of mocked Tibber homes."""
    tibber_home = MagicMock()
    tibber_home.name = "Name"
    tibber_home.home_id = "home_id"
    tibber_home.currency = "NOK"
    tibber_home.has_active_subscription = True
    tibber_home.has_real_time_consumption = False
    tibber_home.country = "NO"
    tibber_home.last_cons_data_timestamp = dt.datetime(2016, 1, 1, 12, 44, 57)
    tibber_home.last_data_timestamp = dt.datetime(2016, 1, 1, 12, 48, 57)

    def get_historic_data(n_data, resolution="HOURLY", production=False):
        return PRODUCTION_DATA_1 if production else CONSUMPTION_DATA_1

    tibber_home.get_historic_data.side_effect = AsyncMock(side_effect=get_historic_data)

    return [tibber_home]


def mock_connection_with_home(access_token, websession, time_zone):
    """Return a mocked Tibber object with mocked home data."""
    tibber_connection = AsyncMock()

    tibber_connection.name = "Mocked Name"
    tibber_connection.access_token = access_token
    tibber_connection.websession = websession
    tibber_connection.time_zone = time_zone

    tibber_connection.update_info = AsyncMock(return_value=None)
    tibber_connection.get_homes = mock_get_homes
    return tibber_connection


def mock_connection(access_token, websession, time_zone):
    """Return a mocked Tibber object."""
    tibber_connection = AsyncMock()

    tibber_connection.name = "Mocked Name"
    tibber_connection.access_token = access_token
    tibber_connection.websession = websession
    tibber_connection.time_zone = time_zone

    tibber_connection.update_info = AsyncMock(return_value=None)

    tibber_connection.get_homes = MagicMock(return_value=[])

    return tibber_connection
