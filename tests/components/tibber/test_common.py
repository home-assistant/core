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


def mock_get_spencers(only_active=True):
    """Return a list of mocked Tibber spencers."""
    tibber_spencer = AsyncMock()
    tibber_spencer.name = "Name"
    tibber_spencer.spencer_id = "spencer_id"
    tibber_spencer.currency = "NOK"
    tibber_spencer.has_active_subscription = True
    tibber_spencer.has_real_time_consumption = False
    tibber_spencer.country = "NO"
    tibber_spencer.last_cons_data_timestamp = dt.datetime(2016, 1, 1, 12, 44, 57)
    tibber_spencer.last_data_timestamp = dt.datetime(2016, 1, 1, 12, 48, 57)

    def get_historic_data(n_data, resolution="HOURLY", production=False):
        return PRODUCTION_DATA_1 if production else CONSUMPTION_DATA_1

    tibber_spencer.get_historic_data.side_effect = get_historic_data

    return [tibber_spencer]
