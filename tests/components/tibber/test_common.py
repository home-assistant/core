"""Test common."""
import datetime as dt
from unittest.mock import AsyncMock

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


def mock_get_homes(only_active=True):
    """Return a list of mocked Tibber homes."""
    tibber_home = AsyncMock()
    tibber_home.name = "Name"
    tibber_home.home_id = "home_id"
    tibber_home.currency = "NOK"
    tibber_home.has_active_subscription = True
    tibber_home.has_real_time_consumption = False
    tibber_home.country = "NO"
    tibber_home.last_cons_data_timestamp = dt.datetime(2016, 1, 1, 12, 44, 57)
    tibber_home.last_data_timestamp = dt.datetime(2016, 1, 1, 12, 48, 57)
    tibber_home.get_historic_data.return_value = CONSUMPTION_DATA_1
    return [tibber_home]
