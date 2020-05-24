"""eafm fixtures."""
# pylint: disable=redefined-outer-name

import asyncio
import datetime

from asynctest import patch
import pytest


@pytest.fixture()
def mock_get_stations():
    """Mock aioeafm.get_stations."""
    with patch("homeassistant.components.eafm.config_flow.get_stations") as patched:

        def set_result(value):
            future = patched.return_value = asyncio.Future()
            if isinstance(value, Exception):
                future.set_exception(value)
            else:
                future.set_result(value)

        yield set_result


@pytest.fixture()
def mock_get_station():
    """Mock aioeafm.get_station."""
    with patch("homeassistant.components.eafm.sensor.get_station") as patched:

        def set_result(value):
            future = patched.return_value = asyncio.Future()
            if isinstance(value, Exception):
                future.set_exception(value)
            else:
                future.set_result(value)

        yield set_result


@pytest.fixture
def utcnow(request):
    """Freeze time at a known point."""
    start_dt = datetime.datetime(2019, 1, 1, 0, 0, 0)
    with patch("homeassistant.util.dt.utcnow") as dt_utcnow:
        dt_utcnow.return_value = start_dt
        yield dt_utcnow
